/** Full-screen step wizard (integrations, add business, etc.). */

/** @type {((value: boolean) => void) | null} */
let appWizardResolve = null;
/** @type {HTMLElement | null} */
let appWizardPreviousFocus = null;

/** @type {{
 *   title: string,
 *   steps: Array<{ id: string, title: string, render: (el: HTMLElement, ctx: object) => void }>,
 *   ctx: object,
 *   index: number,
 *   onFinish?: (ctx: object) => void | Promise<void>,
 * } | null} */
let appWizardState = null;

function getWizardEls() {
  return {
    root: document.getElementById("app-wizard-root"),
    backdrop: document.getElementById("app-wizard-backdrop"),
    panel: document.getElementById("app-wizard-panel"),
    title: document.getElementById("app-wizard-title"),
    stepLabel: document.getElementById("app-wizard-step-label"),
    progress: document.getElementById("app-wizard-progress"),
    body: document.getElementById("app-wizard-body"),
    back: document.getElementById("app-wizard-back"),
    cancel: document.getElementById("app-wizard-cancel"),
    next: document.getElementById("app-wizard-next"),
    close: document.getElementById("app-wizard-close"),
  };
}

function closeAppWizard(completed) {
  const { root, panel } = getWizardEls();
  if (!root || !appWizardResolve) {
    return;
  }
  const resolve = appWizardResolve;
  appWizardResolve = null;
  appWizardState = null;
  void (async () => {
    await uiCloseOverlay(root, "is-open", panel || undefined);
    resolve(completed);
    appWizardPreviousFocus?.focus();
    appWizardPreviousFocus = null;
  })();
}

function renderWizardStep() {
  const state = appWizardState;
  const els = getWizardEls();
  if (!state || !els.body || !els.title || !els.stepLabel || !els.progress || !els.back || !els.next) {
    return;
  }

  const step = state.steps[state.index];
  const total = state.steps.length;
  els.title.textContent = state.title;
  els.stepLabel.textContent = `Step ${state.index + 1} of ${total} · ${step.title}`;
  els.progress.textContent = "";
  for (let i = 0; i < total; i += 1) {
    const dot = document.createElement("span");
    dot.className = "app-wizard-progress-dot";
    if (i === state.index) {
      dot.classList.add("is-current");
    }
    if (i < state.index) {
      dot.classList.add("is-done");
    }
    els.progress.appendChild(dot);
  }

  els.body.innerHTML = "";
  step.render(els.body, state.ctx);

  els.back.hidden = state.index === 0;
  const isLast = state.index === total - 1;
  let finishText = state.finishLabel || "Finish";
  if (isLast && typeof state.finishLabelForCtx === "function") {
    finishText = state.finishLabelForCtx(state.ctx);
  }
  els.next.textContent = isLast ? finishText : "Continue";
}

async function wizardNextClick() {
  const state = appWizardState;
  if (!state) {
    return;
  }
  const step = state.steps[state.index];
  if (typeof step.validate === "function") {
    const result = await step.validate(state.ctx);
    if (result !== true) {
      const msg = typeof result === "string" ? result : "Complete this step to continue.";
      const errEl = document.getElementById("app-wizard-step-error");
      if (errEl) {
        errEl.textContent = msg;
        errEl.hidden = false;
      }
      return;
    }
  }

  if (state.index < state.steps.length - 1) {
    state.index += 1;
    renderWizardStep();
    return;
  }

  const els = getWizardEls();
  if (els.next) {
    els.next.disabled = true;
  }
  try {
    if (state.onFinish) {
      await state.onFinish(state.ctx);
    }
    closeAppWizard(true);
  } catch (err) {
    if (els.next) {
      els.next.disabled = false;
    }
    const errEl = document.getElementById("app-wizard-step-error");
    if (errEl) {
      errEl.textContent = err instanceof Error ? err.message : "Something went wrong.";
      errEl.hidden = false;
    }
  }
}

function wizardBackClick() {
  if (!appWizardState || appWizardState.index === 0) {
    return;
  }
  appWizardState.index -= 1;
  renderWizardStep();
}

function initAppWizard() {
  const els = getWizardEls();
  if (!els.root || !els.backdrop || !els.back || !els.cancel || !els.next || !els.close) {
    return;
  }

  els.backdrop.addEventListener("click", () => closeAppWizard(false));
  els.cancel.addEventListener("click", () => closeAppWizard(false));
  els.close.addEventListener("click", () => closeAppWizard(false));
  els.back.addEventListener("click", wizardBackClick);
  els.next.addEventListener("click", () => {
    void wizardNextClick();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && els.root && uiIsOverlayOpen(els.root, "is-open")) {
      e.preventDefault();
      closeAppWizard(false);
    }
  });
}

/**
 * @param {{
 *   title: string,
 *   finishLabel?: string,
 *   steps: Array<{
 *     id: string,
 *     title: string,
 *     render: (container: HTMLElement, ctx: object) => void,
 *     validate?: (ctx: object) => boolean | string | Promise<boolean | string>,
 *   }>,
 *   ctx?: object,
 *   onFinish?: (ctx: object) => void | Promise<void>,
 *   finishLabelForCtx?: (ctx: object) => string,
 * }} config
 * @returns {Promise<boolean>}
 */
function openAppWizard(config) {
  const els = getWizardEls();
  if (!els.root || !els.body) {
    return Promise.resolve(false);
  }

  return new Promise((resolve) => {
    appWizardPreviousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    appWizardResolve = resolve;
    appWizardState = {
      title: config.title,
      steps: config.steps,
      ctx: config.ctx || {},
      index: 0,
      onFinish: config.onFinish,
      finishLabel: config.finishLabel,
      finishLabelForCtx: config.finishLabelForCtx,
    };
    if (els.next) {
      els.next.disabled = false;
    }
    renderWizardStep();
    void uiOpenOverlay(els.root, "is-open");
  });
}

function wizardPanel(title, paragraphs) {
  const wrap = document.createElement("div");
  wrap.className = "app-wizard-panel";
  const h = document.createElement("h3");
  h.className = "app-wizard-panel-title";
  h.textContent = title;
  wrap.appendChild(h);
  paragraphs.forEach((text) => {
    const p = document.createElement("p");
    p.className = "app-wizard-copy";
    p.textContent = text;
    wrap.appendChild(p);
  });
  const err = document.createElement("p");
  err.className = "app-wizard-error";
  err.id = "app-wizard-step-error";
  err.hidden = true;
  wrap.appendChild(err);
  return wrap;
}

function wizardPrivacyCallout() {
  const box = document.createElement("div");
  box.className = "app-wizard-callout";
  box.innerHTML =
    "<strong>Your credential stays yours.</strong> " +
    "Keys and tokens are encrypted for this business workspace only. " +
    "They are used so the agent can call the provider on your behalf. " +
    "Operators of MultiWorkAgent cannot view your API key after you save it.";
  return box;
}

document.addEventListener("DOMContentLoaded", initAppWizard);
