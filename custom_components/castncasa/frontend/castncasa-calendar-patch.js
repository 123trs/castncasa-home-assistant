customElements.whenDefined("castncasa-time-calendar").then(() => {
  const Card = customElements.get("castncasa-time-calendar");
  if (!Card || Card.prototype.__castncasaRefreshGuardV7Installed) return;
  Card.prototype.__castncasaRefreshGuardV7Installed = true;

  const hassDescriptor = Object.getOwnPropertyDescriptor(Card.prototype, "hass");
  const originalHassSetter = hassDescriptor?.set;
  if (!originalHassSetter) return;

  const originalDisconnected = Card.prototype.disconnectedCallback;
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
      if (isResident) {
        el.style.setProperty("display", "none", "important");
      }
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

  const residentMonthIds = (hass) => Object.keys(hass?.states || {})
    .filter((id) => id.startsWith("calendar.castncasa_"))
    .filter((id) => /Abwesenheit Monat$/i.test(hass.states[id]?.attributes?.friendly_name || ""))
    .sort((a, b) => a.localeCompare(b, "de"));

  const entitySetSignature = (hass) => residentMonthIds(hass).join("|");

  const calendarDataSignature = (hass) => residentMonthIds(hass).map((id) => {
    const state = hass.states[id];
    const a = state?.attributes || {};
    return [id, state?.state || "", state?.last_updated || "", a.message || "", a.start_time || "", a.end_time || ""].join("~");
  }).join("||");

  const getCalendar = (instance) => {
    const full = instance?._findDeep?.(instance._card, "ha-full-calendar");
    return full?.calendar || null;
  };

  const sameMonth = (a, b) => a instanceof Date && b instanceof Date
    && a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth();

  const restoreMonth = (instance, wanted) => {
    if (!(wanted instanceof Date)) return;
    [0, 80, 250, 700, 1400].forEach((delay) => {
      window.setTimeout(() => {
        const fc = getCalendar(instance);
        if (!fc?.getDate || !fc?.gotoDate) return;
        const current = fc.getDate();
        if (!sameMonth(current, wanted)) fc.gotoDate(wanted);
      }, delay);
    });
  };

  const refetchPreservingMonth = (instance) => {
    const fc = getCalendar(instance);
    if (!fc?.refetchEvents) return;
    const current = fc.getDate?.();
    const wanted = current instanceof Date ? new Date(current.getTime()) : null;
    if (instance._card) instance._card.style.visibility = "hidden";
    fc.refetchEvents();
    restoreMonth(instance, wanted);
  };

  const ensurePoll = (instance) => {
    if (instance.__castncasaPollTimer) return;
    instance.__castncasaPollTimer = window.setInterval(() => {
      if (!instance.isConnected || !instance._hass) return;
      const dataSig = calendarDataSignature(instance._hass);
      if (dataSig === instance.__castncasaAppliedDataSig) return;
      instance.__castncasaAppliedDataSig = dataSig;
      refetchPreservingMonth(instance);
    }, 60000);
  };

  Object.defineProperty(Card.prototype, "hass", {
    configurable: true,
    set(hass) {
      const setSig = entitySetSignature(hass);
      const dataSig = calendarDataSignature(hass);

      if (!this.__castncasaGuardInitializedV2) {
        this.__castncasaGuardInitializedV2 = true;
        this.__castncasaEntitySetSigV2 = setSig;
        this.__castncasaAppliedDataSig = dataSig;
        originalHassSetter.call(this, hass);
        ensurePoll(this);
        return;
      }

      this._hass = hass;
      ensurePoll(this);

      if (setSig !== this.__castncasaEntitySetSigV2) {
        const fc = getCalendar(this);
        const current = fc?.getDate?.();
        const wanted = current instanceof Date ? new Date(current.getTime()) : null;
        this.__castncasaEntitySetSigV2 = setSig;
        this.__castncasaAppliedDataSig = dataSig;
        originalHassSetter.call(this, hass);
        restoreMonth(this, wanted);
      }
    }
  });

  Card.prototype.disconnectedCallback = function() {
    if (this.__castncasaPollTimer) {
      window.clearInterval(this.__castncasaPollTimer);
      this.__castncasaPollTimer = null;
    }
    if (typeof originalDisconnected === "function") originalDisconnected.call(this);
  };
});
