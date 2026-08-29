(function () {
  "use strict";

  // Shared helpers from common.js.
  var el = App.el;
  var api = App.api;
  var flash = App.flash;

  var els = {
    district: document.getElementById("f-district"),
    municipality: document.getElementById("f-municipality"),
    archived: document.getElementById("f-archived"),
    addBtn: document.getElementById("btn-add"),
    status: document.getElementById("status"),
    hint: document.getElementById("hint"),
    table: document.getElementById("grid"),
    thead: document.querySelector("#grid thead"),
    tbody: document.querySelector("#grid tbody"),
  };

  var catalog = [];        // [{key,label,group}]
  var trainingCols = [];   // catalog reordered MANAGERIAL then SKILLS (already is)
  var municipalities = []; // [{name,district}]
  var districts = [];      // ordered district names
  var rows = [];           // current personnel

  function setStatus(msg, kind) {
    App.setStatus(els.status, msg, kind);
  }

  function abbr(label) {
    var m = label.match(/\(([^)]+)\)\s*$/);
    return m ? m[1] : label;
  }

  // ---------- boot ----------

  function boot() {
    Promise.all([
      api("GET", "/api/training-catalog/"),
      api("GET", "/api/municipalities/"),
    ]).then(function (res) {
      catalog = res[0];
      trainingCols = catalog.slice();
      municipalities = res[1];
      districts = [];
      municipalities.forEach(function (m) {
        if (districts.indexOf(m.district) === -1) districts.push(m.district);
      });
      districts.forEach(function (d) { els.district.append(el("option", { value: d, text: d })); });

      els.district.addEventListener("change", onDistrictChange);
      els.municipality.addEventListener("change", loadMatrix);
      els.archived.addEventListener("change", loadMatrix);
      els.addBtn.addEventListener("click", openNewPersonnel);
    }).catch(function (e) {
      setStatus("Failed to load reference data: " + e.message, "error");
    });
  }

  function municipalitiesInDistrict(d) {
    return municipalities.filter(function (m) { return m.district === d; });
  }

  function onDistrictChange() {
    var d = els.district.value;
    els.municipality.innerHTML = '<option value="">All municipalities</option>';
    if (d) {
      municipalitiesInDistrict(d).forEach(function (m) {
        els.municipality.append(el("option", { value: m.name, text: m.name }));
      });
      els.municipality.disabled = false;
      els.addBtn.disabled = false;
    } else {
      els.municipality.disabled = true;
      els.addBtn.disabled = true;
    }
    loadMatrix();
  }

  function loadMatrix() {
    var d = els.district.value;
    if (!d) {
      els.table.hidden = true;
      els.hint.hidden = false;
      els.hint.textContent = "Select a district to load the matrix.";
      return;
    }
    var params = new URLSearchParams();
    var mun = els.municipality.value;
    if (mun) params.set("municipality", mun);
    else params.set("district", d);
    if (els.archived.value) params.set("archived", els.archived.value);

    setStatus("Loading…");
    api("GET", "/api/personnel/?" + params.toString()).then(function (data) {
      rows = data || [];
      setStatus("");
      renderTable();
    }).catch(function (e) {
      setStatus("Load failed: " + e.message, "error");
    });
  }

  // ---------- table ----------

  function renderTable() {
    var archivedMode = !!els.archived.value;
    var showMunicipality = !els.municipality.value;

    var managerial = trainingCols.filter(function (c) { return c.group === "MANAGERIAL"; });
    var skills = trainingCols.filter(function (c) { return c.group === "SKILLS"; });

    // header — two full rows, no rowspan (rowspan + sticky collapses in Chrome).
    // Row 1: group bands over blank "corner" cells. Row 2: every column label.
    els.thead.innerHTML = "";
    var leadRest = 3 + (showMunicipality ? 1 : 0); // Designation, Employment Status, Org Affiliation [, Municipality]

    var r1 = el("tr", { class: "band-row" });
    r1.append(el("th", { class: "col-name corner" }));
    r1.append(el("th", { class: "corner", colspan: String(leadRest) }));
    r1.append(el("th", { class: "band band-managerial", colspan: String(managerial.length) },
      el("span", { class: "band-label", text: "MANAGERIAL" })));
    r1.append(el("th", { class: "band band-skills", colspan: String(skills.length) },
      el("span", { class: "band-label", text: "SKILLS" })));
    r1.append(el("th", { class: "corner", colspan: "2" })); // Other DRR Training + actions
    els.thead.append(r1);

    var r2 = el("tr", { class: "label-row" });
    r2.append(el("th", { class: "col-name", text: "Name" }));
    r2.append(el("th", { text: "Designation" }));
    r2.append(el("th", { text: "Employment Status" }));
    r2.append(el("th", { text: "Org Affiliation" }));
    if (showMunicipality) r2.append(el("th", { text: "Municipality" }));
    managerial.concat(skills).forEach(function (c) {
      r2.append(el("th", { class: "train-h", title: c.label, text: abbr(c.label) }));
    });
    r2.append(el("th", { text: "Other DRR Training" }));
    r2.append(el("th", { text: "" }));
    els.thead.append(r2);

    // body
    els.tbody.innerHTML = "";
    if (!rows.length) {
      els.table.hidden = true;
      els.hint.hidden = false;
      els.hint.textContent = archivedMode
        ? "No archived personnel in this scope."
        : "No personnel in this scope yet — use “+ New Personnel”.";
      return;
    }
    els.hint.hidden = true;
    els.table.hidden = false;

    var cols = managerial.concat(skills);
    rows.forEach(function (p) {
      els.tbody.append(buildRow(p, cols, showMunicipality, archivedMode));
    });
  }

  function buildRow(p, cols, showMunicipality, archivedMode) {
    var tr = el("tr");
    tr.setAttribute("data-id", String(p.id));

    tr.append(identityCell(p, "name", "col-name"));
    tr.append(identityCell(p, "designation"));
    tr.append(identityCell(p, "employment_status"));
    tr.append(affiliationCell(p));
    if (showMunicipality) tr.append(el("td", { text: p.municipality }));

    var byKey = {};
    p.training_records.forEach(function (rec) { byKey[rec.training_key] = rec.year_attained; });
    cols.forEach(function (c) { tr.append(yearCell(p, c.key, byKey[c.key])); });

    tr.append(identityCell(p, "other_drr_training", "other", true));

    var td = el("td", { class: "row-actions" });
    if (archivedMode) {
      td.append(el("button", { type: "button", text: "Restore", onclick: function () { restore(p); } }));
    } else {
      td.append(el("button", { type: "button", class: "danger", text: "Archive", onclick: function () { archive(p); } }));
    }
    tr.append(td);
    return tr;
  }

  function currentText(p, field) {
    return p[field] == null ? "" : String(p[field]);
  }

  function identityCell(p, field, cls, isTextarea) {
    var td = el("td", { class: "id-cell " + (cls || "") });
    var input = isTextarea ? el("textarea", { rows: "1" }) : el("input", { type: "text" });
    input.value = currentText(p, field);
    input.addEventListener("change", function () {
      if (input.value === currentText(p, field)) return;
      var patch = {};
      patch[field] = input.value;
      savePersonnel(p, patch, input, field);
    });
    td.append(input);
    return td;
  }

  function affiliationCell(p) {
    var td = el("td", { class: "id-cell" });
    var sel = el("select");
    sel.append(el("option", { value: "EMPLOYEE", text: "Employee" }));
    sel.append(el("option", { value: "VOLUNTEER", text: "Volunteer" }));
    sel.value = p.org_affiliation;
    sel.addEventListener("change", function () {
      savePersonnel(p, { org_affiliation: sel.value }, sel, "org_affiliation");
    });
    td.append(sel);
    return td;
  }

  function yearCell(p, key, year) {
    var td = el("td", { class: "year-cell" });
    var input = el("input", { type: "number", min: "2000", max: "2035", step: "1", class: "year", placeholder: "–" });
    input.value = year != null ? String(year) : "";
    input.dataset.current = year != null ? String(year) : "";
    input.addEventListener("change", function () { saveCell(p, key, input); });
    td.append(input);
    return td;
  }

  // ---------- mutations ----------

  function savePersonnel(p, patch, control, field) {
    if (control) control.classList.add("saving");
    api("PATCH", "/api/personnel/" + p.id + "/", patch).then(function (updated) {
      Object.assign(p, updated);
      if (control) { control.classList.remove("saving"); flash(control, "ok"); }
      setStatus("Saved", "ok");
    }).catch(function (e) {
      if (control) {
        control.classList.remove("saving");
        flash(control, "error");
        if ("value" in control && field) control.value = currentText(p, field);
      }
      setStatus("Save failed: " + e.message, "error");
    });
  }

  function saveCell(p, key, input) {
    var raw = input.value.trim();
    var prev = input.dataset.current;
    if (raw === prev) return;
    input.classList.add("saving");

    var done = function (newVal) {
      input.classList.remove("saving");
      input.value = newVal;
      input.dataset.current = newVal;
      syncLocalRecord(p, key, newVal === "" ? null : parseInt(newVal, 10));
      flash(input, "ok");
      setStatus("Saved", "ok");
    };
    var fail = function (e) {
      input.classList.remove("saving");
      input.value = prev;
      flash(input, "error");
      setStatus("Cell save failed (" + key + "): " + e.message, "error");
    };

    if (raw === "") {
      api("PATCH", "/api/personnel/" + p.id + "/training-record/" + key + "/", { year_attained: null })
        .then(function () { done(""); }).catch(fail);
    } else {
      api("PATCH", "/api/personnel/" + p.id + "/training-record/" + key + "/", { year_attained: parseInt(raw, 10) })
        .then(function (rec) { done(String(rec.year_attained)); }).catch(fail);
    }
  }

  function syncLocalRecord(p, key, year) {
    var i = p.training_records.findIndex(function (r) { return r.training_key === key; });
    if (year == null) { if (i !== -1) p.training_records.splice(i, 1); return; }
    if (i === -1) p.training_records.push({ training_key: key, year_attained: year });
    else p.training_records[i].year_attained = year;
  }

  function archive(p) {
    if (!window.confirm("Archive " + p.name + "? They'll be hidden from the active matrix (not deleted).")) return;
    api("DELETE", "/api/personnel/" + p.id + "/")
      .then(function () { setStatus("Archived", "ok"); loadMatrix(); })
      .catch(function (e) { setStatus("Archive failed: " + e.message, "error"); });
  }

  function restore(p) {
    api("POST", "/api/personnel/" + p.id + "/restore/")
      .then(function () { setStatus("Restored", "ok"); loadMatrix(); })
      .catch(function (e) { setStatus("Restore failed: " + e.message, "error"); });
  }

  function openNewPersonnel() {
    var tpl = document.getElementById("tpl-new-personnel");
    var node = tpl.content.firstElementChild.cloneNode(true);
    var form = node.querySelector("form");
    var munSel = form.querySelector('select[name="municipality"]');
    municipalitiesInDistrict(els.district.value).forEach(function (m) {
      munSel.append(el("option", { value: m.name, text: m.name }));
    });
    if (els.municipality.value) munSel.value = els.municipality.value;

    node.addEventListener("click", function (e) { if (e.target === node) node.remove(); });
    form.querySelector("[data-cancel]").addEventListener("click", function () { node.remove(); });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = {};
      new FormData(form).forEach(function (v, k) { data[k] = v; });
      api("POST", "/api/personnel/", data).then(function () {
        node.remove();
        setStatus("Created", "ok");
        loadMatrix();
      }).catch(function (err) {
        window.alert("Create failed: " + err.message);
      });
    });
    document.body.append(node);
    form.querySelector('input[name="name"]').focus();
  }

  boot();
})();
