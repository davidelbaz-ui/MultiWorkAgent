function initPasswordToggles() {
  document.querySelectorAll(".password-field").forEach((wrap) => {
    const input = wrap.querySelector(".password-input, input[type='password']");
    const btn = wrap.querySelector(".password-toggle");
    if (!input || !btn || btn.dataset.bound === "1") {
      return;
    }
    btn.dataset.bound = "1";
    const showIcon = btn.querySelector(".password-toggle-icon--show");
    const hideIcon = btn.querySelector(".password-toggle-icon--hide");

    const setVisible = (visible) => {
      input.type = visible ? "text" : "password";
      btn.setAttribute("aria-pressed", visible ? "true" : "false");
      btn.setAttribute("aria-label", visible ? "Hide password" : "Show password");
      if (showIcon) {
        showIcon.hidden = visible;
      }
      if (hideIcon) {
        hideIcon.hidden = !visible;
      }
    };

    btn.addEventListener("click", () => {
      setVisible(input.type === "password");
    });
  });
}

document.addEventListener("DOMContentLoaded", initPasswordToggles);
