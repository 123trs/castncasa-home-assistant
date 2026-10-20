customElements.whenDefined("castncasa-time-calendar").then(() => {
  const Card = customElements.get("castncasa-time-calendar");
  if (!Card || Card.prototype.__castncasaDesktopTextV1Installed) return;
  Card.prototype.__castncasaDesktopTextV1Installed = true;

  const originalAddSegment = Card.prototype._addSegment;
  if (typeof originalAddSegment !== "function") return;

  Card.prototype._addSegment = function(el, leftPct, widthPct, color, label) {
    originalAddSegment.call(this, el, leftPct, widthPct, color, label);

    if (!window.matchMedia?.("(min-width: 1024px)")?.matches) return;

    const segments = el?.querySelectorAll?.(".castncasa-timebar-segment");
    const segment = segments?.[segments.length - 1];
    const text = segment?.querySelector?.("span");
    if (!text) return;

    text.style.fontWeight = "800";

    if (widthPct < 10) {
      text.style.fontSize = "10px";
      text.style.transform = "scaleX(.85)";
    } else if (widthPct < 18) {
      text.style.fontSize = "11px";
      text.style.transform = "none";
    } else if (widthPct < 28) {
      text.style.fontSize = "11px";
      text.style.transform = "none";
    } else {
      text.style.fontSize = "12px";
      text.style.transform = "none";
    }
  };
});