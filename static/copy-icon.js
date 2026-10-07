/** Thin overlapping-documents copy icon (stroke, currentColor). */
(function initCopyIcon(global) {
  const COPY_ICON_PATHS = [
    "M9.25 6.75h8.25a1.25 1.25 0 0 1 1.25 1.25v9.25a1.25 1.25 0 0 1-1.25 1.25H9.25",
    "M5.75 9.75h8.25a1.25 1.25 0 0 1 1.25 1.25v9.25a1.25 1.25 0 0 1-1.25 1.25H6.75A1.25 1.25 0 0 1 5.5 18.25V11A1.25 1.25 0 0 1 6.75 9.75H5.75",
  ];

  function createCopyIconSvg() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "msg-action-icon msg-action-icon--copy");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.35");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    COPY_ICON_PATHS.forEach((d) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  }

  global.createCopyIconSvg = createCopyIconSvg;
})(window);
