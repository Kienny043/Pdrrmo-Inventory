(function () {
  "use strict";
  var app = document.getElementById("app");
  if (!app) return;

  var el = App.el;
  var api = App.api;
  var els = {
    status: document.getElementById("status"),
    tbody: document.getElementById("tbody"),
    empty: document.getElementById("empty"),
    addBtn: document.getElementById("btn-add"),
    tpl: document.getElementById("tpl-staff-form"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  function load() {
    api("GET", "/api/staff/")
      .then(render)
      .catch(function (e) { status("Load failed: " + e.message, "error"); });
  }

  function render(rows) {
    els.tbody.innerHTML = "";
    els.empty.hidden = rows.length > 0;
    rows.forEach(function (s) { els.tbody.append(rowFor(s)); });
  }

  function rowFor(s) {
    var tr = el("tr");
    var photoCell = el("td");
    if (s.photo) photoCell.append(el("img", { class: "thumb", src: s.photo, alt: "" }));
    else photoCell.textContent = "—";
    tr.append(photoCell);
    tr.append(el("td", { text: s.full_name }));
    tr.append(el("td", { text: s.position || "—" }));
    tr.append(el("td", { text: s.department || "—" }));
    tr.append(el("td", { text: s.contact || "—" }));
    tr.append(el("td", { text: s.status }));
    var actions = el("td", { class: "actions" });
    actions.append(el("button", { type: "button", text: "Edit", onclick: function () { openForm(s); } }));
    actions.append(
      el("button", { type: "button", class: "danger", text: "Archive", onclick: function () { archive(s); } })
    );
    tr.append(actions);
    return tr;
  }

  function openForm(existing) {
    var form = els.tpl.content.firstElementChild.cloneNode(true);
    var errBox = form.querySelector("[data-error]");
    var removeWrap = form.querySelector("[data-remove-wrap]");

    if (existing) {
      form.querySelector("[data-title]").textContent = "Edit " + existing.full_name;
      ["first_name", "last_name", "position", "department", "contact", "status"].forEach(function (f) {
        form.elements[f].value = existing[f] == null ? "" : existing[f];
      });
      if (existing.photo) removeWrap.hidden = false;
    }

    App.openModal(form, function (f, close) {
      errBox.textContent = "";
      var fd = new FormData();
      ["first_name", "last_name", "position", "department", "contact", "status"].forEach(function (name) {
        fd.append(name, f.elements[name].value);
      });
      var file = f.elements.photo.files[0];
      if (file) fd.append("photo", file);
      if (existing && f.elements.remove_photo && f.elements.remove_photo.checked) {
        fd.append("remove_photo", "true");
      }
      var method = existing ? "PATCH" : "POST";
      var url = existing ? "/api/staff/" + existing.id + "/" : "/api/staff/";
      api(method, url, fd)
        .then(function () {
          close();
          status(existing ? "Updated" : "Created", "ok");
          load();
        })
        .catch(function (e) { errBox.textContent = e.message; });
    });
  }

  function archive(s) {
    if (!window.confirm("Archive " + s.full_name + "? They'll move to the Archived page.")) return;
    api("DELETE", "/api/staff/" + s.id + "/")
      .then(function () { status("Archived", "ok"); load(); })
      .catch(function (e) { status("Archive failed: " + e.message, "error"); });
  }

  els.addBtn.addEventListener("click", function () { openForm(null); });
  load();
})();
