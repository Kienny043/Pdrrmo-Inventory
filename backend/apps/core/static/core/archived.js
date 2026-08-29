(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var canDelete = app.dataset.canDelete === "1";

  var els = {
    tabs: document.getElementById("tabs"),
    thead: document.getElementById("thead"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
    status: document.getElementById("status"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }
  function fdate(v) { return v ? String(v).slice(0, 10) : "—"; }

  // One data-driven config per tab — no per-tab logic. Every archivable
  // resource exposes the same <base>/<id>/restore/ and
  // <base>/<id>/permanent-delete/ shape.
  var TABS = [
    {
      key: "items", label: "Items",
      url: "/api/items/archived/", base: "/api/items/",
      cols: [
        { h: "Name", f: "name" }, { h: "Brand", f: "brand" },
        { h: "Category", f: "category_name" }, { h: "Qty", f: "quantity" },
        { h: "Condition", f: "condition" }, { h: "Archived", f: "archived_at", fmt: fdate },
      ],
    },
    {
      key: "staff", label: "Staff",
      url: "/api/staff/archived/", base: "/api/staff/",
      cols: [
        { h: "Name", f: "full_name" }, { h: "Position", f: "position" },
        { h: "Department", f: "department" }, { h: "Status", f: "status" },
        { h: "Archived", f: "archived_at", fmt: fdate },
      ],
    },
    {
      key: "trainings", label: "Trainings",
      url: "/api/trainings/archived/", base: "/api/trainings/",
      cols: [
        { h: "Title", f: "title" }, { h: "Start", f: "date_start" },
        { h: "Status", f: "status" }, { h: "Matrix training", f: "matrix_training_label" },
        { h: "Archived", f: "archived_at", fmt: fdate },
      ],
    },
    {
      key: "personnel", label: "Personnel",
      url: "/api/personnel/?archived=true", base: "/api/personnel/",
      cols: [
        { h: "Name", f: "name" }, { h: "Designation", f: "designation" },
        { h: "Municipality", f: "municipality" }, { h: "District", f: "district" },
        { h: "Archived", f: "archived_at", fmt: fdate },
      ],
    },
  ];
  var active = TABS[0];

  TABS.forEach(function (tab) {
    var b = el("button", { type: "button", text: tab.label, onclick: function () { select(tab); } });
    if (tab === active) b.className = "active";
    b.dataset.tab = tab.key;
    els.tabs.append(b);
  });

  function select(tab) {
    active = tab;
    [].forEach.call(els.tabs.children, function (b) {
      b.className = b.dataset.tab === tab.key ? "active" : "";
    });
    load();
  }

  function load() {
    status("Loading…");
    api("GET", active.url)
      .then(function (rows) {
        rows = rows || [];
        status("");
        renderHead();
        els.tbody.innerHTML = "";
        els.empty.hidden = rows.length > 0;
        rows.forEach(function (r) { els.tbody.append(rowFor(r)); });
      })
      .catch(function (e) { status("Load failed: " + e.message, "error"); });
  }

  function renderHead() {
    els.thead.innerHTML = "";
    var tr = el("tr");
    active.cols.forEach(function (c) { tr.append(el("th", { text: c.h })); });
    tr.append(el("th", { text: "", style: "width:14rem" }));
    els.thead.append(tr);
  }

  function cell(r, c) {
    var v = r[c.f];
    if (c.fmt) return c.fmt(v);
    return v == null || v === "" ? "—" : String(v);
  }

  function rowFor(r) {
    var tr = el("tr");
    active.cols.forEach(function (c) { tr.append(el("td", { text: cell(r, c) })); });
    var td = el("td", { class: "actions" });
    td.append(el("button", { type: "button", text: "Restore", onclick: function () { restore(r); } }));
    if (canDelete) {
      td.append(el("button", {
        type: "button", class: "danger", text: "Delete permanently",
        onclick: function () { permaDelete(r); },
      }));
    }
    tr.append(td);
    return tr;
  }

  function labelOf(r) {
    return r.name || r.title || r.full_name || "#" + r.id;
  }

  function restore(r) {
    api("POST", active.base + r.id + "/restore/")
      .then(function () { status("Restored", "ok"); load(); })
      .catch(function (e) { status("Restore failed: " + e.message, "error"); });
  }

  function permaDelete(r) {
    if (!window.confirm('Permanently delete "' + labelOf(r) + '"? This cannot be undone.')) return;
    api("DELETE", active.base + r.id + "/permanent-delete/")
      .then(function () { status("Permanently deleted", "ok"); load(); })
      .catch(function (e) { status("Delete failed: " + e.message, "error"); });
  }

  load();
})();
