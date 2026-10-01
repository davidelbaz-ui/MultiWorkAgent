const UI_MOTION_MS = 220;

function uiReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function uiAfterTransition(element, maxMs = UI_MOTION_MS + 80) {
  return new Promise((resolve) => {
    if (!element || uiReducedMotion()) {
      resolve();
      return;
    }
    let settled = false;
    const done = () => {
      if (settled) {
        return;
      }
      settled = true;
      element.removeEventListener("transitionend", onEnd);
      clearTimeout(timer);
      resolve();
    };
    const onEnd = (e) => {
      if (e.target === element) {
        done();
      }
    };
    element.addEventListener("transitionend", onEnd);
    const timer = setTimeout(done, maxMs);
  });
}

async function uiOpenOverlay(root, visibleClass = "is-open") {
  if (!root) {
    return;
  }
  root.hidden = false;
  root.removeAttribute("hidden");
  root.setAttribute("aria-hidden", "false");
  root.classList.remove(visibleClass);
  if (uiReducedMotion()) {
    root.classList.add(visibleClass);
    return;
  }
  await new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
  root.classList.add(visibleClass);
}

async function uiCloseOverlay(root, visibleClass = "is-open", transitionTarget = null) {
  if (!root) {
    return;
  }
  root.classList.remove(visibleClass);
  const motionEl = transitionTarget || root.querySelector(".app-dialog") || root;
  if (!uiReducedMotion()) {
    await uiAfterTransition(motionEl);
  }
  root.hidden = true;
  root.setAttribute("aria-hidden", "true");
}

async function uiShowElement(element) {
  if (!element) {
    return;
  }
  element.hidden = false;
  element.removeAttribute("hidden");
  element.classList.remove("ui-motion-visible");
  if (uiReducedMotion()) {
    element.classList.add("ui-motion-visible");
    return;
  }
  await new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  });
  element.classList.add("ui-motion-visible");
}

async function uiHideElement(element) {
  if (!element || element.hidden) {
    return;
  }
  element.classList.remove("ui-motion-visible");
  if (!uiReducedMotion()) {
    await uiAfterTransition(element);
  }
  element.hidden = true;
}

function uiIsOverlayOpen(root, visibleClass = "is-open") {
  return Boolean(root && root.classList.contains(visibleClass));
}
