/** Thin overlapping-documents copy icon (stroke, currentColor). */
(function initCopyIcon(global) {
  const COPY_ICON_PATHS = [
    "M8.5 7.5H7A1.5 1.5 0 0 0 5.5 9v11A1.5 1.5 0 0 0 7 21.5h9A1.5 1.5 0 0 0 17.5 20V18.5",
    "M15.5 5.5h1.5A1.5 1.5 0 0 1 18.5 7v11a1.5 1.5 0 0 1-1.5 1.5H8.5A1.5 1.5 0 0 1 7 18V7a1.5 1.5 0 0 1 1.5-1.5h7",
  ];

  function createCopyIconSvg() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "msg-action-icon msg-action-icon--copy");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    COPY_ICON_PATHS.forEach((d) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      path.setAttribute("stroke", "currentColor");
      path.setAttribute("fill", "none");
      svg.appendChild(path);
    });
    return svg;
  }

  global.createCopyIconSvg = createCopyIconSvg;
  global.COPY_ICON_PATHS = COPY_ICON_PATHS;
})(window);
