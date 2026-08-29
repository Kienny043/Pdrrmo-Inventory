/* Shared vanilla-JS helpers for the plain-template pages (Step 7a). */
window.App = (function () {
  "use strict";

  function getCookie(name) {
    var m = document.cookie.match("(^|; )" + name + "=([^;]*)");
    return m ? decodeURIComponent(m[2]) : "";
  }
  var CSRF = getCookie("csrftoken");

  function summarise(obj) {
    try {
      return Object.keys(obj)
        .map(function (k) {
          var v = obj[k];
          return (k === "detail" || k === "non_field_errors" ? "" : k + ": ") +
            [].concat(v).join(" ");
        })
        .join("; ");
    } catch (e) {
      return String(obj);
    }
  }

  function api(method, url, body) {
    var opts = {
      method: method,
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    };
    if (body instanceof FormData) {
      opts.body = body; // browser sets multipart Content-Type + boundary
    } else if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    if (method !== "GET" && method !== "HEAD") opts.headers["X-CSRFToken"] = CSRF;
    return fetch(url, opts).then(function (resp) {
      if (resp.status === 204) return null;
      return resp
        .json()
        .catch(function () { return null; })
        .then(function (data) {
          if (!resp.ok) {
            var msg =
              (data && (data.detail || summarise(data))) ||
              resp.status + " " + resp.statusText;
            var err = new Error(msg);
            err.status = resp.status;
            err.data = data;
            throw err;
          }
          return data;
        });
    });
  }

  function el(tag, attrs) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k === "html") node.innerHTML = v;
        else if (k in node) node[k] = v;
        else node.setAttribute(k, v);
      });
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c != null) node.append(c);
    }
    return node;
  }

  function setStatus(node, msg, kind) {
    if (!node) return;
    node.textContent = msg || "";
    node.className = "status" + (kind ? " " + kind : "");
    if (kind === "ok") {
      var snap = msg;
      setTimeout(function () {
        if (node.textContent === snap) {
          node.textContent = "";
          node.className = "status";
        }
      }, 1500);
    }
  }

  function flash(node, kind) {
    if (!node) return;
    node.classList.add("flash-" + kind);
    setTimeout(function () { node.classList.remove("flash-" + kind); }, 900);
  }

  /* Wrap a <form> in a backdrop and show it. onSubmit(form, close) runs on
     submit; the caller decides when to call close() (keep open on error). */
  function openModal(formNode, onSubmit) {
    var backdrop = el("div", { class: "modal-backdrop" });
    backdrop.append(formNode);
    function close() { backdrop.remove(); }
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) close();
    });
    var cancel = formNode.querySelector("[data-cancel]");
    if (cancel) cancel.addEventListener("click", close);
    if (formNode.tagName === "FORM" && onSubmit) {
      formNode.addEventListener("submit", function (e) {
        e.preventDefault();
        onSubmit(formNode, close);
      });
    }
    document.body.append(backdrop);
    var first = formNode.querySelector("input, select, textarea");
    if (first) first.focus();
    return { close: close, backdrop: backdrop };
  }

  function downloadCsv(filename, rows, columns) {
    function cell(v) {
      v = v == null ? "" : String(v);
      return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
    }
    var head = columns.map(function (c) { return cell(c.label); }).join(",");
    var body = rows
      .map(function (r) {
        return columns
          .map(function (c) { return cell(c.get ? c.get(r) : r[c.key]); })
          .join(",");
      })
      .join("\n");
    var blob = new Blob([head + "\n" + body], { type: "text/csv;charset=utf-8" });
    var a = el("a", { href: URL.createObjectURL(blob), download: filename });
    document.body.append(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      a.remove();
    }, 0);
  }

  return {
    CSRF: CSRF,
    getCookie: getCookie,
    api: api,
    el: el,
    setStatus: setStatus,
    flash: flash,
    summarise: summarise,
    openModal: openModal,
    downloadCsv: downloadCsv,
  };
})();
