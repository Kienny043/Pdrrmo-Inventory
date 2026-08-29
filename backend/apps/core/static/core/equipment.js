(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var canEdit = app.dataset.canEdit === "1";

  var els = {
    status: document.getElementById("status"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
    category: document.getElementById("f-category"),
    search: document.getElementById("f-search"),
    addBtn: document.getElementById("btn-add"),
    csvBtn: document.getElementById("btn-csv"),
    itemTpl: document.getElementById("tpl-item-form"),
    histTpl: document.getElementById("tpl-history"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  var items = [];
  var categories = [];
  var staff = [];

  function load() {
    var jobs = [api("GET", "/api/items/"), api("GET", "/api/categories/")];
    if (canEdit) jobs.push(api("GET", "/api/staff/"));
    return Promise.all(jobs)
      .then(function (res) {
        items = res[0] || [];
        categories = res[1] || [];
        staff = res[2] || [];
        var current = els.category.value;
        els.category.innerHTML = '<option value="">All categories</option>';
        categories.forEach(function (c) {
          els.category.append(el("option", { value: String(c.id), text: c.name }));
        });
        els.category.value = current;
        render();
      })
      .catch(function (e) { status("Load failed: " + e.message, "error"); });
  }

  function visibleRows() {
    var cat = els.category.value;
    var q = els.search.value.trim().toLowerCase();
    return items.filter(function (it) {
      if (cat && String(it.category) !== cat) return false;
      if (q) {
        var hay = ((it.name || "") + " " + (it.brand || "")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
  }

  function render() {
    var rows = visibleRows();
    els.tbody.innerHTML = "";
    els.empty.hidden = rows.length > 0;
    rows.forEach(function (it) { els.tbody.append(rowFor(it)); });
  }

  function rowFor(it) {
    var tr = el("tr");
    [
      it.name,
      it.brand || "—",
      it.category_name,
      String(it.quantity),
      it.unit || "—",
      it.condition,
      it.memorandum_receipt_name || "—",
      it.remarks || "—",
      it.date_acquired || "—",
    ].forEach(function (v) { tr.append(el("td", { text: v })); });

    if (canEdit) {
      var actions = el("td", { class: "actions" });
      actions.append(el("button", { type: "button", text: "Edit", onclick: function () { openForm(it); } }));
      actions.append(el("button", { type: "button", text: "History", onclick: function () { openHistory(it); } }));
      actions.append(el("button", { type: "button", class: "danger", text: "Archive", onclick: function () { archive(it); } }));
      tr.append(actions);
    }
    return tr;
  }

  function archive(it) {
    if (!window.confirm("Archive “" + it.name + "”? It moves to the Archived page.")) return;
    api("DELETE", "/api/items/" + it.id + "/")
      .then(function () { status("Archived", "ok"); load(); })
      .catch(function (e) { status("Archive failed: " + e.message, "error"); });
  }

  function openForm(existing) {
    var form = els.itemTpl.content.firstElementChild.cloneNode(true);
    var errBox = form.querySelector("[data-error]");
    var catSel = form.elements.category;
    var holderSel = form.elements.memorandum_receipt;
    categories.forEach(function (c) {
      catSel.append(el("option", { value: String(c.id), text: c.name }));
    });
    staff.forEach(function (s) {
      holderSel.append(el("option", { value: String(s.id), text: s.full_name }));
    });

    if (existing) {
      form.querySelector("[data-title]").textContent = "Edit " + existing.name;
      ["name", "brand", "unit", "condition", "remarks"].forEach(function (f) {
        form.elements[f].value = existing[f] == null ? "" : existing[f];
      });
      form.elements.date_acquired.value = existing.date_acquired || "";
      catSel.value = String(existing.category);
      holderSel.value = existing.memorandum_receipt ? String(existing.memorandum_receipt) : "";
      form.elements.quantity.value = String(existing.quantity);
      form.elements.quantity.disabled = true; // create-only (serializer strips on PATCH)
    }

    App.openModal(form, function (f, close) {
      errBox.textContent = "";
      var data = {
        name: f.elements.name.value,
        brand: f.elements.brand.value,
        category: Number(catSel.value),
        unit: f.elements.unit.value,
        condition: f.elements.condition.value,
        remarks: f.elements.remarks.value,
        date_acquired: f.elements.date_acquired.value || null,
        memorandum_receipt: holderSel.value ? Number(holderSel.value) : null,
      };
      if (!existing) data.quantity = Number(f.elements.quantity.value);

      var method = existing ? "PATCH" : "POST";
      var url = existing ? "/api/items/" + existing.id + "/" : "/api/items/";
      api(method, url, data)
        .then(function (saved) {
          var file = f.elements.image.files[0];
          if (!file) return saved;
          var fd = new FormData();
          fd.append("image", file);
          return api("PATCH", "/api/items/" + saved.id + "/", fd);
        })
        .then(function () {
          close();
          status(existing ? "Updated" : "Created", "ok");
          load();
        })
        .catch(function (e) { errBox.textContent = e.message; });
    });
  }

  function openHistory(it) {
    api("GET", "/api/items/" + it.id + "/holder-history/")
      .then(function (logs) {
        var node = els.histTpl.content.firstElementChild.cloneNode(true);
        node.querySelector("[data-title]").textContent = "Holder history — " + it.name;
        var body = node.querySelector("[data-rows]");
        node.querySelector("[data-empty]").hidden = logs.length > 0;
        logs.forEach(function (h) {
          var tr = el("tr");
          [h.timestamp, h.action, h.staff_name || "—", h.performed_by || "—", h.note || "—"].forEach(function (v) {
            tr.append(el("td", { text: v }));
          });
          body.append(tr);
        });
        App.openModal(node);
      })
      .catch(function (e) { status("History failed: " + e.message, "error"); });
  }

  var CSV_COLS = [
    { label: "name", key: "name" },
    { label: "brand", key: "brand" },
    { label: "category", get: function (r) { return r.category_name; } },
    { label: "quantity", key: "quantity" },
    { label: "unit", key: "unit" },
    { label: "condition", key: "condition" },
    { label: "holder", get: function (r) { return r.memorandum_receipt_name || ""; } },
    { label: "date_acquired", key: "date_acquired" },
    { label: "remarks", key: "remarks" },
  ];
  function exportCsv() {
    App.downloadCsv("equipment.csv", visibleRows(), CSV_COLS);
    status("CSV exported", "ok");
  }

  // one-time wiring
  els.category.addEventListener("change", render);
  els.search.addEventListener("input", render);
  els.csvBtn.addEventListener("click", exportCsv);
  if (els.addBtn) els.addBtn.addEventListener("click", function () { openForm(null); });

  load();
})();
