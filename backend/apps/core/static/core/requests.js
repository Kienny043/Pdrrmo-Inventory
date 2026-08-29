(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var isAdmin = app.dataset.isAdmin === "1";

  var form = document.getElementById("request-form");
  var els = {
    form: form,
    itemSelect: form.querySelector('select[name="item"]'), // not form.elements.item
    qty: form.querySelector('input[name="quantity"]'),
    note: form.querySelector('input[name="note"]'),
    status: document.getElementById("status"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  function loadItems() {
    return api("GET", "/api/items/").then(function (rows) {
      els.itemSelect.innerHTML = "";
      (rows || []).forEach(function (it) {
        els.itemSelect.append(
          el("option", { value: String(it.id), text: it.name + " (on hand: " + it.quantity + ")" })
        );
      });
    });
  }

  function loadList() {
    return api("GET", "/api/requests/").then(function (rows) {
      els.tbody.innerHTML = "";
      els.empty.hidden = rows.length > 0;
      rows.forEach(function (r) { els.tbody.append(rowFor(r)); });
    });
  }

  function refresh() {
    return Promise.all([loadItems(), loadList()]).catch(function (e) {
      status("Load failed: " + e.message, "error");
    });
  }

  function decidedText(r) {
    if (!r.decided_by) return "—";
    return r.decided_by + (r.decided_at ? " · " + r.decided_at.slice(0, 10) : "");
  }

  function rowFor(r) {
    var tr = el("tr");
    [r.item_name, String(r.quantity), r.status, r.note || "—", r.requested_by, decidedText(r)].forEach(
      function (v) { tr.append(el("td", { text: v })); }
    );

    if (isAdmin) {
      var td = el("td", { class: "actions" });
      if (r.status === "PENDING") {
        td.append(el("button", { type: "button", text: "Approve", onclick: function () { decide(r, "APPROVED", td); } }));
        td.append(el("button", { type: "button", class: "danger", text: "Reject", onclick: function () { decide(r, "REJECTED", td); } }));
        td.append(el("div", { class: "form-error", "data-err": "" }));
      }
      // non-PENDING rows: no controls at all
      tr.append(td);
    }
    return tr;
  }

  function decide(r, decision, td) {
    var errBox = td.querySelector("[data-err]");
    if (errBox) errBox.textContent = "";
    td.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
    api("PATCH", "/api/requests/" + r.id + "/approve/", { decision: decision })
      .then(function () {
        status(decision === "APPROVED" ? "Approved" : "Rejected", "ok");
        refresh();
      })
      .catch(function (e) {
        // insufficient stock (400) / already-decided (409): show it next to the
        // row; the request stays as it was.
        if (errBox) errBox.textContent = e.message;
        else status(e.message, "error");
        td.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
      });
  }

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    var body = {
      item: Number(els.itemSelect.value),
      quantity: Number(els.qty.value),
      note: els.note.value,
    };
    api("POST", "/api/requests/", body)
      .then(function () {
        els.qty.value = "1";
        els.note.value = "";
        status("Request submitted", "ok");
        refresh();
      })
      .catch(function (e) { status("Submit failed: " + e.message, "error"); });
  });

  refresh();
})();
