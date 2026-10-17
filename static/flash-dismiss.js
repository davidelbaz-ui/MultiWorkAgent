const PAGE_FLASH_DISMISS_PREFIX = "mwa.pageFlashDismissed.";

function getDismissedFlashId(persistKey) {
  try {
    return localStorage.getItem(PAGE_FLASH_DISMISS_PREFIX + persistKey);
  } catch {
    return null;
  }
}

function setDismissedFlashId(persistKey, persistId) {
  try {
    localStorage.setItem(PAGE_FLASH_DISMISS_PREFIX + persistKey, persistId);
  } catch {
    /* ignore quota / private mode */
  }
}

function applyPersistedFlashDismissals() {
  document.querySelectorAll(".page-flash[data-flash-persist-key]").forEach((flash) => {
    const persistKey = flash.dataset.flashPersistKey;
    const persistId = flash.dataset.flashPersistId;
    if (!persistKey || !persistId) {
      return;
    }
    if (getDismissedFlashId(persistKey) === persistId) {
      flash.remove();
    }
  });
}

function initDismissiblePageFlashes() {
  applyPersistedFlashDismissals();
  document.querySelectorAll(".page-flash__dismiss").forEach((btn) => {
    if (btn.dataset.flashBound === "1") {
      return;
    }
    btn.dataset.flashBound = "1";
    btn.addEventListener("click", () => {
      const flash = btn.closest(".page-flash");
      if (flash) {
        const persistKey = flash.dataset.flashPersistKey;
        const persistId = flash.dataset.flashPersistId;
        if (persistKey && persistId) {
          setDismissedFlashId(persistKey, persistId);
        }
        flash.remove();
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initDismissiblePageFlashes);
