customElements.whenDefined("castncasa-time-calendar").then(() => {
  const Card = customElements.get("castncasa-time-calendar");
  if (!Card || Card.prototype.__castncasaMobilePatchV8Installed) return;
  Card.prototype.__castncasaMobilePatchV8Installed = true;

  const originalStyleMonthEvent = Card.prototype._styleMonthEvent;
  const originalTuneCalendar = Card.prototype._tuneCalendar;

  const isMobile = () => window.matchMedia?.("(max-width: 700px)")?.matches;

  const deepFindAll = (root, selector, out = []) => {
    if (!root) return out;
    try {
      if (root.querySelectorAll) out.push(...root.querySelectorAll(selector));
      const all = root.querySelectorAll?.("*") || [];
      for (const el of all) {
        if (el.shadowRoot) deepFindAll(el.shadowRoot, selector, out);
      }
      if (root.shadowRoot) deepFindAll(root.shadowRoot, selector, out);
    } catch (_) {}
    return out;
  };

  const colorForEvent = (event) => event?.backgroundColor || event?.borderColor || "#607d8b";

  const dateKey = (date) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return null;
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  };

  const visibleMonthBounds = (fc) => {
    const anchor = fc?.getDate?.() || fc?.view?.currentStart;
    if (!(anchor instanceof Date) || Number.isNaN(anchor.getTime())) return null;
    const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1);
    return { start: start.getTime(), end: end.getTime() };
  };

  const renderMobileStacks = (instance, fc) => {
    if (!isMobile() || !fc) return;
    const full = instance?._findDeep?.(instance._card, "ha-full-calendar");
    if (!full) return;

    deepFindAll(full, ".castncasa-mobile-resident-stack").forEach((node) => node.remove());

    const residentOrder = new Map((instance._residentInfo || []).map((item, idx) => [item.id, idx]));
    const bounds = visibleMonthBounds(fc);
    const byDay = new Map();

    for (const event of fc.getEvents?.() || []) {
      const entityId = event.extendedProps?.calendar || "";
      if (!residentOrder.has(entityId)) continue;
      const start = event.start;
      const ts = start?.getTime?.();
      if (!Number.isFinite(ts)) continue;
      if (bounds && (ts < bounds.start || ts >= bounds.end)) continue;
      const key = dateKey(start);
      if (!key) continue;
      const list = byDay.get(key) || [];
      list.push({
        entityId,
        label: instance._shortCode?.(event.title) || "",
        color: colorForEvent(event),
      });
      byDay.set(key, list);
    }

    for (const [key, items] of byDay.entries()) {
      const dayCell = instance._findDeep?.(full, `[data-date="${key}"]`);
      if (!dayCell) continue;
      const target = instance._findDeep?.(dayCell, ".fc-daygrid-day-events")
        || instance._findDeep?.(dayCell, ".fc-daygrid-day-frame")
        || dayCell;

      const stack = document.createElement("div");
      stack.className = "castncasa-mobile-resident-stack";
      stack.style.display = "flex";
      stack.style.flexDirection = "column";
      stack.style.alignItems = "center";
      stack.style.gap = "2px";
      stack.style.margin = "2px 0 0 0";
      stack.style.padding = "0";
      stack.style.position = "relative";
      stack.style.zIndex = "4";
      stack.style.width = "100%";
      stack.style.pointerEvents = "none";

      items.sort((a, b) => {
        const ai = residentOrder.get(a.entityId) ?? 999;
        const bi = residentOrder.get(b.entityId) ?? 999;
        if (ai !== bi) return ai - bi;
        return a.label.localeCompare(b.label, "de");
      });

      for (const item of items) {
        const chip = document.createElement("div");
        chip.textContent = item.label;
        chip.style.display = "flex";
        chip.style.alignItems = "center";
        chip.style.justifyContent = "center";
        chip.style.boxSizing = "border-box";
        chip.style.minWidth = "34px";
        chip.style.maxWidth = "44px";
        chip.style.height = "18px";
        chip.style.padding = "0 6px";
        chip.style.borderRadius = "7px";
        chip.style.background = item.color;
        chip.style.color = "#fff";
        chip.style.fontSize = "10px";
        chip.style.fontWeight = "700";
        chip.style.lineHeight = "18px";
        chip.style.whiteSpace = "nowrap";
        chip.style.overflow = "hidden";
        chip.style.textOverflow = "ellipsis";
        chip.style.boxShadow = "none";
        stack.appendChild(chip);
      }

      target.appendChild(stack);
    }
  };

  if (typeof originalStyleMonthEvent === "function") {
    Card.prototype._styleMonthEvent = function(info) {
      originalStyleMonthEvent.call(this, info);

      if (!isMobile()) return;
      const el = info?.el;
      const entityId = info?.event?.extendedProps?.calendar || "";
      if (!el) return;

      if (entityId === "calendar.castncasa_feiertage") {
        const title = el.querySelector(".fc-event-title");
        const frame = el.querySelector(".fc-event-main-frame");
        const main = el.querySelector(".fc-event-main");
        if (title) {
          title.textContent = "FT";
          title.style.setProperty("padding", "0 4px", "important");
          title.style.setProperty("text-align", "center", "important");
          title.style.setProperty("font-size", "11px", "important");
          title.style.setProperty("font-weight", "700", "important");
          title.style.setProperty("white-space", "nowrap", "important");
          title.style.setProperty("color", "#fff", "important");
        }
        if (frame) {
          frame.style.setProperty("justify-content", "center", "important");
          frame.style.setProperty("min-height", "17px", "important");
        }
        if (main) {
          main.style.setProperty("min-height", "17px", "important");
          main.style.setProperty("text-align", "center", "important");
        }
        el.style.setProperty("border-radius", "7px", "important");
        return;
      }

      const isResident = this._residentInfo?.some((item) => item.id === entityId);
      if (isResident) el.style.setProperty("display", "none", "important");
    };
  }

  if (typeof originalTuneCalendar === "function") {
    Card.prototype._tuneCalendar = function() {
      originalTuneCalendar.call(this);
      if (!isMobile()) return;
      const full = this._findDeep?.(this._card, "ha-full-calendar");
      const fc = full?.calendar;
      if (!fc) return;
      window.requestAnimationFrame(() => renderMobileStacks(this, fc));
    };
  }
});
