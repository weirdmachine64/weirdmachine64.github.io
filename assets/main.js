// weirdmachine: client interactions (progressive enhancement)
(function () {
  "use strict";

  // --- syntax highlighting -------------------------------------------------
  if (window.hljs) {
    document.querySelectorAll("pre code").forEach(function (el) {
      try { window.hljs.highlightElement(el); } catch (e) {}
    });
  }

  // --- copy buttons on code blocks -----------------------------------------
  document.querySelectorAll(".code__copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var code = btn.closest(".code").querySelector("code");
      if (!code) return;
      var text = code.innerText;
      var done = function () {
        btn.textContent = "copied";
        btn.classList.add("done");
        setTimeout(function () { btn.textContent = "copy"; btn.classList.remove("done"); }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); } catch (e) {}
        document.body.removeChild(ta); done();
      }
    });
  });

  // --- tag filtering on the research page ----------------------------------
  var filters = document.querySelectorAll(".filter");
  var cards = document.querySelectorAll(".cards--list .card");
  filters.forEach(function (f) {
    f.addEventListener("click", function () {
      var tag = f.getAttribute("data-tag");
      filters.forEach(function (x) { x.classList.remove("is-active"); });
      f.classList.add("is-active");
      cards.forEach(function (c) {
        var tags = (c.getAttribute("data-tags") || "").split(" ");
        var show = tag === "*" || tags.indexOf(tag) !== -1;
        c.classList.toggle("is-hidden", !show);
      });
    });
  });

  // --- live project stars/forks (refresh on load) --------------------------
  var grid = document.querySelector(".cards[data-gh-user]");
  if (grid && window.fetch) {
    var user = grid.getAttribute("data-gh-user");
    fetch("https://api.github.com/users/" + user + "/repos?per_page=100", {
      headers: { "Accept": "application/vnd.github+json" }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (list) {
        if (!Array.isArray(list)) return;
        var map = {};
        list.forEach(function (x) {
          map[x.name.toLowerCase()] = { s: x.stargazers_count, f: x.forks_count };
        });
        grid.querySelectorAll(".project[data-repo]").forEach(function (card) {
          var d = map[(card.getAttribute("data-repo") || "").toLowerCase()];
          if (!d) return;
          var s = card.querySelector('[data-stat="stars"] .project__n');
          var f = card.querySelector('[data-stat="forks"] .project__n');
          if (s) s.textContent = d.s;
          if (f) f.textContent = d.f;
        });
      })
      .catch(function () { /* keep build-time values */ });
  }

  // --- footer clock --------------------------------------------------------
  var clock = document.getElementById("clock");
  if (clock) {
    var tick = function () {
      var d = new Date();
      clock.textContent = d.toISOString().slice(0, 19).replace("T", " ") + "Z";
    };
    tick(); setInterval(tick, 1000);
  }
})();
