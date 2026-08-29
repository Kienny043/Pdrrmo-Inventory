(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var form = document.getElementById("record-form");
  var els = {
    form: form,
    // form.elements.item would resolve to the collection's item() method
    itemSelect: form.querySelector('select[name="item"]'),
    typeSelect: form.querySelector('select[name="movement_type"]'),
    qtyInput: form.querySelector('input[name="quantity"]'),
    noteInput: form.querySelector('input[name="note"]'),
    formError: document.getElementById("form-error"),
    status: document.getElementById("status"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
    itemFilter: document.getElementById("f-item"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  var items = [];

  function loadItems() {
    return api("GET", "/api/items/").then(function (rows) {
      items = rows || [];
      var filterVal = els.itemFilter.value;
      els.itemSelect.innerHTML = "";
      els.itemFilter.innerHTML = '<option value="">All items</option>';
      items.forEach(function (it) {
        var label = it.name + " (on hand: " + it.quantity + ")";
        els.itemSelect.append(el("option", { value: String(it.id), text: label }));
        els.itemFilter.append(el("option", { value: String(it.id), text: it.name }));
      });
      els.itemFilter.value = filterVal;
    });
  }

  function loadLog() {
    var q = els.itemFilter.value ? "?item=" + els.itemFilter.value : "";
    return api("GET", "/api/movements/" + q).then(function (rows) {
      els.tbody.innerHTML = "";
      els.empty.hidden = rows.length > 0;
      rows.forEach(function (m) {
        var tr = el("tr");
        [m.created_at, m.item_name, m.movement_type, String(m.quantity), m.note || "—", m.performed_by || "—"].forEach(
          function (v) { tr.append(el("td", { text: v })); }
        );
        els.tbody.append(tr);
      });
    });
  }

  function refresh() {
    return loadItems().then(loadLog).catch(function (e) {
      status("Load failed: " + e.message, "error");
    });
  }

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    els.formError.textContent = "";
    var body = {
      item: Number(els.itemSelect.value),
      movement_type: els.typeSelect.value,
      quantity: Number(els.qtyInput.value),
      note: els.noteInput.value,
    };
    api("POST", "/api/movements/add/", body)
      .then(function () {
        els.qtyInput.value = "1";
        els.noteInput.value = "";
        status("Recorded", "ok");
        refresh();
      })
      .catch(function (err) {
        // insufficient stock (400) and any other error land here — show the
        // server's message right on the form, not just a transient flash.
        els.formError.textContent = err.message;
      });
  });

  els.itemFilter.addEventListener("change", function () {
    loadLog().catch(function (e) { status("Load failed: " + e.message, "error"); });
  });

  refresh();
})();
