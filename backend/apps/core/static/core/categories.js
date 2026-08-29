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
    newName: document.getElementById("new-name"),
    newDesc: document.getElementById("new-desc"),
    addBtn: document.getElementById("btn-add"),
  };
  function status(msg, kind) { App.setStatus(els.status, msg, kind); }

  function load() {
    api("GET", "/api/categories/")
      .then(render)
      .catch(function (e) { status("Load failed: " + e.message, "error"); });
  }

  function render(rows) {
    els.tbody.innerHTML = "";
    els.empty.hidden = rows.length > 0;
    rows.forEach(function (c) { els.tbody.append(rowFor(c)); });
  }

  function inlineField(c, field) {
    var input = el("input", { type: "text", class: "cell-input", value: c[field] == null ? "" : c[field] });
    input.addEventListener("change", function () {
      var next = input.value;
      if (next === (c[field] == null ? "" : String(c[field]))) return;
      var patch = {};
      patch[field] = next;
      input.classList.add("saving");
      api("PATCH", "/api/categories/" + c.id + "/", patch)
        .then(function (updated) {
          Object.assign(c, updated);
          input.classList.remove("saving");
          App.flash(input, "ok");
          status("Saved", "ok");
        })
        .catch(function (e) {
          input.classList.remove("saving");
          input.value = c[field] == null ? "" : c[field];
          App.flash(input, "error");
          status("Save failed: " + e.message, "error");
        });
    });
    return input;
  }

  function rowFor(c) {
    var tr = el("tr");
    tr.append(el("td", null, inlineField(c, "name")));
    tr.append(el("td", null, inlineField(c, "description")));
    tr.append(el("td", { text: String(c.item_count) }));
    var actions = el("td", { class: "actions" });
    actions.append(
      el("button", {
        type: "button",
        class: "danger",
        text: "Delete",
        onclick: function () { remove(c); },
      })
    );
    tr.append(actions);
    return tr;
  }

  function remove(c) {
    if (!window.confirm("Delete category “" + c.name + "”?")) return;
    api("DELETE", "/api/categories/" + c.id + "/")
      .then(function () { status("Deleted", "ok"); load(); })
      .catch(function (e) { status(e.message, "error"); });
  }

  els.addBtn.addEventListener("click", function () {
    var name = els.newName.value.trim();
    if (!name) { status("Name is required.", "error"); return; }
    api("POST", "/api/categories/", { name: name, description: els.newDesc.value })
      .then(function () {
        els.newName.value = "";
        els.newDesc.value = "";
        status("Created", "ok");
        load();
      })
      .catch(function (e) { status(e.message, "error"); });
  });
  els.newName.addEventListener("keydown", function (e) {
    if (e.key === "Enter") els.addBtn.click();
  });

  load();
})();
