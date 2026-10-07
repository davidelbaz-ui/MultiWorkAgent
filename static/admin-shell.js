function initAdminMobileShell() {
  const shell = document.getElementById("admin-shell");
  const toggle = document.getElementById("admin-nav-toggle");
  const backdrop = document.getElementById("admin-nav-backdrop");
  const sidebar = document.getElementById("admin-sidebar");
  if (!shell || !toggle || !backdrop || !sidebar) {
    return;
  }

  const close = () => {
    shell.classList.remove("admin-nav-open");
    document.body.classList.remove("admin-nav-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open admin menu");
    backdrop.setAttribute("hidden", "");
    backdrop.setAttribute("aria-hidden", "true");
  };

  const open = () => {
    shell.classList.add("admin-nav-open");
    document.body.classList.add("admin-nav-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close admin menu");
    backdrop.removeAttribute("hidden");
    backdrop.setAttribute("aria-hidden", "false");
  };

  toggle.addEventListener("click", () => {
    if (shell.classList.contains("admin-nav-open")) {
      close();
    } else {
      open();
    }
  });

  backdrop.addEventListener("click", close);

  sidebar.querySelectorAll(".admin-nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 960px)").matches) {
        close();
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && shell.classList.contains("admin-nav-open")) {
      close();
    }
  });

  window.matchMedia("(min-width: 961px)").addEventListener("change", (e) => {
    if (e.matches) {
      close();
    }
  });
}

document.addEventListener("DOMContentLoaded", initAdminMobileShell);
