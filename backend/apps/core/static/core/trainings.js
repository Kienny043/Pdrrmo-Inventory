(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var isAdmin = app.dataset.isAdmin === "1";
  var canDelete = app.dataset.canDelete === "1";

  var els = {
    status: document.getElementById("status"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
    addBtn: document.getElementById("btn-add"),
    view: document.getElementById("f-view"),
    trainingTpl: document.getElementById("tpl-training-form"),
    manualTpl: document.getElementById("tpl-manual-form"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  var catalog = [];
  var municipalities = [];
  var trainings = [];
  var openPanelId = null;

  var LEAD_COLS = 9; // for the panel-row colspan

  function boot() {
    Promise.all([api("GET", "/api/training-catalog/"), api("GET", "/api/municipalities/")])
      .then(function (res) {
        catalog = res[0] || [];
        municipalities = res[1] || [];
        return loadTrainings();
      })
      .catch(function (e) { status("Load failed: " + e.message, "error"); });

    if (els.addBtn) els.addBtn.addEventListener("click", function () { openForm(null); });
    if (els.view) els.view.addEventListener("change", function () { openPanelId = null; loadTrainings(); });
  }

  function archivedView() { return els.view && els.view.value === "archived"; }

  function loadTrainings() {
    var url = archivedView() ? "/api/trainings/archived/" : "/api/trainings/";
    return api("GET", url).then(function (rows) {
      trainings = rows || [];
      render();
    });
  }

  function render() {
    els.tbody.innerHTML = "";
    els.empty.hidden = trainings.length > 0;
    trainings.forEach(function (t) {
      els.tbody.append(rowFor(t));
      if (openPanelId === t.id) els.tbody.append(panelRow(t));
    });
  }

  function fmtDates(t) {
    var d = t.date_start + (t.date_end && t.date_end !== t.date_start ? " – " + t.date_end : "");
    var time = t.time_start ? " " + t.time_start.slice(0, 5) + (t.time_end ? "–" + t.time_end.slice(0, 5) : "") : "";
    return d + time;
  }

  function todayISO() { return new Date().toISOString().slice(0, 10); }

  function registerBlock(t) {
    if (t.is_archived) return "training is archived";
    if (t.status !== "UPCOMING" && t.status !== "ONGOING") return "registration closed (" + t.status.toLowerCase() + ")";
    if (t.registration_deadline && t.registration_deadline < todayISO()) return "registration deadline passed";
    if (t.max_slots != null && t.registration_count >= t.max_slots) return "training is full";
    if (t.my_registration_status === "REGISTERED") return "you are already registered";
    return null;
  }

  function rowFor(t) {
    var tr = el("tr", { "data-id": String(t.id) });
    [
      t.title,
      fmtDates(t),
      t.venue || "—",
      t.status,
      t.matrix_training_label || "—",
      t.max_slots == null ? "—" : String(t.max_slots),
      t.registration_deadline || "—",
      String(t.registration_count),
    ].forEach(function (v) { tr.append(el("td", { text: v })); });

    var td = el("td", { class: "actions" });

    // register / cancel (both roles)
    if (t.my_registration_status === "REGISTERED") {
      td.append(el("button", { type: "button", text: "Cancel registration", onclick: function () { cancelReg(t); } }));
    } else {
      var reason = registerBlock(t);
      var btn = el("button", { type: "button", text: "Register", onclick: function () { register(t, td); } });
      if (reason) { btn.disabled = true; td.append(btn); td.append(el("span", { class: "reg-hint", text: reason })); }
      else td.append(btn);
    }
    if (t.my_registration_status) {
      td.append(el("span", { class: "reg-hint", text: "you: " + t.my_registration_status }));
    }

    if (isAdmin) {
      if (archivedView()) {
        td.append(el("button", { type: "button", text: "Restore", onclick: function () { restore(t); } }));
        if (canDelete) td.append(el("button", { type: "button", class: "danger", text: "Delete", onclick: function () { permaDelete(t); } }));
      } else {
        td.append(el("button", { type: "button", text: openPanelId === t.id ? "Hide" : "Details", onclick: function () { togglePanel(t); } }));
        td.append(el("button", { type: "button", text: "Edit", onclick: function () { openForm(t); } }));
        td.append(el("button", { type: "button", class: "danger", text: "Archive", onclick: function () { archive(t); } }));
      }
    }
    tr.append(td);
    return tr;
  }

  // ---- expandable panel (ADMIN) ----

  function togglePanel(t) {
    openPanelId = openPanelId === t.id ? null : t.id;
    render();
    if (openPanelId === t.id) fillPanel(t);
  }

  function panelRow(t) {
    var tr = el("tr", { class: "panel-row", "data-panel-for": String(t.id) });
    var td = el("td", { colspan: String(LEAD_COLS) });
    td.append(el("div", { class: "panel", "data-panel": "" },
      el("p", { class: "hint", text: "Loading…" })));
    tr.append(td);
    return tr;
  }

  function fillPanel(t) {
    var host = els.tbody.querySelector('tr.panel-row[data-panel-for="' + t.id + '"] [data-panel]');
    if (!host) return;
    Promise.all([
      api("GET", "/api/trainings/" + t.id + "/registrations/"),
      api("GET", "/api/trainings/" + t.id + "/manual-attendees/"),
    ])
      .then(function (res) {
        host.innerHTML = "";
        host.append(rosterSection(t, res[0] || []));
        host.append(manualSection(t, res[1] || []));
      })
      .catch(function (e) { host.innerHTML = ""; host.append(el("p", { class: "form-error", text: e.message })); });
  }

  function rosterSection(t, regs) {
    var box = el("div");
    box.append(el("h3", { text: "Registrations" }));
    if (!regs.length) { box.append(el("p", { class: "hint", text: "No registrations." })); return box; }
    var tbl = el("table", { class: "sub-table" });
    tbl.append(el("thead", null, el("tr", null,
      el("th", { text: "User" }), el("th", { text: "Status" }),
      el("th", { text: "Registered" }), el("th", { text: "Cancelled" }),
      el("th", { text: "Attended" }))));
    var body = el("tbody");
    regs.forEach(function (r) {
      var tr = el("tr");
      tr.append(el("td", { text: r.user }));
      tr.append(el("td", { text: r.status }));
      tr.append(el("td", { text: (r.registered_at || "").slice(0, 10) }));
      tr.append(el("td", { text: r.cancelled_at ? r.cancelled_at.slice(0, 10) : "—" }));
      var attTd = el("td");
      var cb = el("input", { type: "checkbox", checked: !!r.attended });
      var note = el("span", { class: "attend-note" });
      cb.addEventListener("change", function () { attendToggle(t, r, cb, note); });
      attTd.append(cb, note);
      tr.append(attTd);
      body.append(tr);
    });
    tbl.append(body);
    box.append(tbl);
    return box;
  }

  function attendToggle(t, r, cb, note) {
    cb.disabled = true;
    note.textContent = "…";
    note.className = "attend-note";
    api("PATCH", "/api/trainings/" + t.id + "/attendance/" + r.user_id + "/", { attended: cb.checked })
      .then(function (resp) {
        cb.disabled = false;
        if (!cb.checked) { note.textContent = "attendance cleared"; note.className = "attend-note"; return; }
        if (resp.matrix_updated) { note.textContent = "✓ matrix updated"; note.className = "attend-note ok"; }
        else { note.textContent = "matrix not updated — " + (resp.matrix_reason || "no reason given"); note.className = "attend-note warn"; }
      })
      .catch(function (e) {
        cb.checked = !cb.checked;
        cb.disabled = false;
        note.textContent = "";
        status(e.message, "error");
      });
  }

  function manualSection(t, attendees) {
    var box = el("div");
    box.append(el("h3", { text: "Manual attendees" }));
    box.append(el("p", { class: "manual-note", text: "Manual attendees do not feed the training matrix — their attendance is a plain record." }));

    var tbl = el("table", { class: "sub-table" });
    tbl.append(el("thead", null, el("tr", null,
      el("th", { text: "Name" }), el("th", { text: "Designation" }),
      el("th", { text: "Municipality" }), el("th", { text: "District" }),
      el("th", { text: "Affiliation" }), el("th", { text: "Attended" }), el("th", { text: "" }))));
    var body = el("tbody");
    attendees.forEach(function (a) {
      var tr = el("tr");
      [a.name, a.designation || "—", a.municipality, a.district || "—", a.org_affiliation].forEach(function (v) {
        tr.append(el("td", { text: v }));
      });
      var attTd = el("td");
      var cb = el("input", { type: "checkbox", checked: !!a.attended });
      cb.addEventListener("change", function () {
        cb.disabled = true;
        api("PATCH", "/api/trainings/" + t.id + "/manual-attendees/" + a.id + "/attendance/", { attended: cb.checked })
          .then(function () { cb.disabled = false; status("Attendance saved", "ok"); })
          .catch(function (e) { cb.checked = !cb.checked; cb.disabled = false; status(e.message, "error"); });
      });
      attTd.append(cb);
      tr.append(attTd);
      var delTd = el("td");
      delTd.append(el("button", { type: "button", class: "danger", text: "Delete", onclick: function () { deleteManual(t, a); } }));
      tr.append(delTd);
      body.append(tr);
    });
    tbl.append(body);
    box.append(tbl);

    var form = els.manualTpl.content.firstElementChild.cloneNode(true);
    var munSel = form.querySelector('select[name="municipality"]');
    municipalities.forEach(function (m) { munSel.append(el("option", { value: m.name, text: m.name })); });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = {};
      new FormData(form).forEach(function (v, k) { data[k] = v; });
      api("POST", "/api/trainings/" + t.id + "/manual-attendees/", data)
        .then(function () { status("Attendee added", "ok"); fillPanel(t); })
        .catch(function (err) { status("Add failed: " + err.message, "error"); });
    });
    box.append(form);
    return box;
  }

  function deleteManual(t, a) {
    if (!window.confirm("Delete manual attendee “" + a.name + "”?")) return;
    api("DELETE", "/api/trainings/" + t.id + "/manual-attendees/" + a.id + "/")
      .then(function () { status("Deleted", "ok"); fillPanel(t); })
      .catch(function (e) { status(e.message, "error"); });
  }

  // ---- create / edit ----

  function openForm(existing) {
    var form = els.trainingTpl.content.firstElementChild.cloneNode(true);
    var errBox = form.querySelector("[data-error]");
    var catSel = form.querySelector("[data-catalog]");
    var mgr = el("optgroup", { label: "MANAGERIAL" });
    var skl = el("optgroup", { label: "SKILLS" });
    catalog.forEach(function (c) {
      (c.group === "SKILLS" ? skl : mgr).append(el("option", { value: c.key, text: c.label }));
    });
    catSel.append(mgr, skl);

    var scalarFields = ["title", "description", "date_start", "date_end", "time_start", "time_end",
      "venue", "target_participants", "max_slots", "registration_deadline", "status"];
    if (existing) {
      form.querySelector("[data-title]").textContent = "Edit " + existing.title;
      scalarFields.forEach(function (f) {
        var v = existing[f];
        if (f === "time_start" || f === "time_end") v = v ? v.slice(0, 5) : "";
        form.elements[f].value = v == null ? "" : v;
      });
      catSel.value = existing.matrix_training_key || "";
    }

    App.openModal(form, function (f, close) {
      errBox.textContent = "";
      var data = {};
      scalarFields.forEach(function (name) {
        var v = f.elements[name].value;
        if (name === "max_slots") data[name] = v === "" ? null : Number(v);
        else if ((name === "date_end" || name === "registration_deadline" ||
                  name === "time_start" || name === "time_end") && v === "") data[name] = null;
        else data[name] = v;
      });
      data.matrix_training_key = catSel.value;
      var method = existing ? "PATCH" : "POST";
      var url = existing ? "/api/trainings/" + existing.id + "/" : "/api/trainings/";
      api(method, url, data)
        .then(function () { close(); status(existing ? "Updated" : "Created", "ok"); loadTrainings(); })
        .catch(function (e) { errBox.textContent = e.message; });
    });
  }

  // ---- register / cancel ----

  function register(t, td) {
    api("POST", "/api/trainings/" + t.id + "/register/")
      .then(function () { status("Registered", "ok"); loadTrainings(); })
      .catch(function (e) {
        // server is authoritative about the 5 blockers — show its reason
        if (td) { var h = el("span", { class: "reg-hint", text: e.message }); td.append(h); }
        status(e.message, "error");
      });
  }

  function cancelReg(t) {
    if (!window.confirm("Cancel your registration for “" + t.title + "”?")) return;
    api("DELETE", "/api/trainings/" + t.id + "/cancel-registration/")
      .then(function () { status("Registration cancelled", "ok"); loadTrainings(); })
      .catch(function (e) { status(e.message, "error"); });
  }

  // ---- archive lifecycle ----

  function archive(t) {
    if (!window.confirm("Archive “" + t.title + "”?")) return;
    api("DELETE", "/api/trainings/" + t.id + "/")
      .then(function () { status("Archived", "ok"); openPanelId = null; loadTrainings(); })
      .catch(function (e) { status(e.message, "error"); });
  }
  function restore(t) {
    api("POST", "/api/trainings/" + t.id + "/restore/")
      .then(function () { status("Restored", "ok"); loadTrainings(); })
      .catch(function (e) { status(e.message, "error"); });
  }
  function permaDelete(t) {
    if (!window.confirm("Permanently delete “" + t.title + "”? This cannot be undone.")) return;
    api("DELETE", "/api/trainings/" + t.id + "/permanent-delete/")
      .then(function () { status("Permanently deleted", "ok"); loadTrainings(); })
      .catch(function (e) { status(e.message, "error"); });
  }

  boot();
})();
