(function () {
  function navigate(href) {
    if (href) window.location.href = href;
  }

  document.querySelectorAll(".admin-table-row--clickable").forEach(function (row) {
    row.addEventListener("click", function (event) {
      if (event.target.closest("a, button, input, select, label")) return;
      navigate(row.getAttribute("data-href"));
    });
    row.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        navigate(row.getAttribute("data-href"));
      }
    });
  });
})();
