function initDismissiblePageFlashes() {
  document.querySelectorAll(".page-flash__dismiss").forEach((btn) => {
    if (btn.dataset.flashBound === "1") {
      return;
    }
    btn.dataset.flashBound = "1";
    btn.addEventListener("click", () => {
      const flash = btn.closest(".page-flash");
      if (flash) {
        flash.remove();
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initDismissiblePageFlashes);
