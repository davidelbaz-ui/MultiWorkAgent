function initPasswordToggles() {
  document.querySelectorAll(".password-field").forEach((wrap) => {
    const input = wrap.querySelector(".password-input");
    const btn = wrap.querySelector(".password-toggle");
    if (!input || !btn || btn.dataset.bound === "1") {
      return;
    }
    btn.dataset.bound = "1";

    const setVisible = (visible) => {
      input.type = visible ? "text" : "password";
      btn.classList.toggle("is-revealed", visible);
      btn.setAttribute("aria-pressed", visible ? "true" : "false");
      btn.setAttribute("aria-label", visible ? "Hide password" : "Show password");
    };

    btn.addEventListener("click", () => {
      setVisible(input.type === "password");
    });
  });
}

document.addEventListener("DOMContentLoaded", initPasswordToggles);
