class CastnCasaTimeCalendar extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this._entitiesKey = "";
    this._card = null;
    this._buildId = 0;
    this._residentInfo = [];
    this._hookedCalendar = null;
  }

  set hass(hass) {
    this._hass = hass;
    const all = Object.keys(hass.states)
      .filter((id) => id.startsWith("calendar.castncasa_"))
      .sort((a, b) => a.localeCompare(b, "de"));

    const monthly = all.filter((id) => {
      const friendly = hass.states[id]?.attributes?.friendly_name || "";
      return /Abwesenheit Monat$/i.test(friendly);
    });
    const regular = all.filter((id) => {
      const friendly = hass.states[id]?.attributes?.friendly_name || "";
      return /(Abwesenheit|Dienstplan)$/i.test(friendly) && !/Abwesenheit Monat$/i.test(friendly);
    });

    const isMonth = (this.config.initial_view || "dayGridMonth") === "dayGridMonth";
    const residents = isMonth && monthly.length ? monthly : regular;

    const residentInfo = residents.map((id) => {
      const friendly = hass.states[id]?.attributes?.friendly_name || id;
      const name = friendly
        .replace(/^CastnCasa\s*·\s*/i, "")
        .replace(/\s+(Abwesenheit Monat|Abwesenheit|Dienstplan)$/i, "")
        .trim();
      return { id, name };
    });
    this._residentInfo = residentInfo;

    const entities = [...residents];
    if (this.config.include_holidays !== false && hass.states["calendar.castncasa_feiertage"]) {
      entities.push("calendar.castncasa_feiertage");
    }

    const key = JSON.stringify({ entities, names: residentInfo.map((item) => item.name), title: this.config.title });
    if (!this._card || key !== this._entitiesKey) {
      this._entitiesKey = key;
      this._createCalendar(entities, residentInfo);
    } else {
      this._card.hass = hass;
      this._scheduleTune();
    }
  }

  async _createCalendar(entities, residentInfo) {
    const buildId = ++this._buildId;
    const helpers = await window.loadCardHelpers();
    if (buildId !== this._buildId) return;

    const cardConfig = {
      type: "calendar",
      entities,
      initial_view: this.config.initial_view || "dayGridMonth",
      show_add_event: false,
    };
    if (this.config.card_mod) cardConfig.card_mod = this.config.card_mod;

    const card = helpers.createCardElement(cardConfig);
    card.style.visibility = "hidden";

    const header = document.createElement("div");
    header.className = "castncasa-calendar-header";
    const title = document.createElement("div");
    title.className = "castncasa-calendar-title";
    title.textContent = this.config.title || "Abwesenheit · Alle Bewohner";
    const legend = document.createElement("div");
    legend.className = "castncasa-resident-legend";

    residentInfo.forEach((item) => {
      const block = document.createElement("div");
      block.className = "castncasa-resident-block";
      block.dataset.entity = item.id;

      const chip = document.createElement("span");
      chip.className = "castncasa-resident-chip";
      chip.dataset.entity = item.id;
      chip.textContent = item.name;
      chip.style.background = this._fallbackColor(item.name);
      chip.style.color = "#fff";

      const shifts = document.createElement("div");
      shifts.className = "castncasa-shift-list";
      shifts.dataset.entity = item.id;

      block.append(chip, shifts);
      legend.appendChild(block);
    });
    header.append(title, legend);

    const style = document.createElement("style");
    style.textContent = `
      .castncasa-calendar-header {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 8px 14px 6px;
        min-height: 38px;
      }
      .castncasa-calendar-title {
        font-size: 20px;
        font-weight: 500;
        line-height: 1.2;
        white-space: nowrap;
        padding-top: 2px;
      }
      .castncasa-resident-legend {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-start;
        gap: 12px;
        margin-left: 2px;
      }
      .castncasa-resident-block {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 3px;
        min-width: 96px;
      }
      .castncasa-resident-chip {
        display: inline-flex;
        align-items: center;
        padding: 4px 11px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 800;
        line-height: 1.2;
        color: #fff;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,.08);
      }
      .castncasa-shift-list {
        display: flex;
        flex-direction: column;
        gap: 1px;
        padding-left: 3px;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.3;
        white-space: nowrap;
      }
      .castncasa-shift-entry { opacity: .82; }
      @media (max-width: 700px) {
        .castncasa-calendar-header { align-items: flex-start; flex-direction: column; gap: 8px; }
        .castncasa-calendar-title { font-size: 18px; }
        .castncasa-resident-legend { gap: 9px 12px; }
        .castncasa-resident-block { min-width: 88px; }
        .castncasa-shift-list { font-size: 11px; }
      }
    `;

    this.replaceChildren(style, header, card);
    this._card = card;
    if (this._hass) this._card.hass = this._hass;
    this._scheduleTune();
  }

  _fallbackColor(name) {
    const n = String(name || "").toLocaleLowerCase("de");
    const palette = ["#2e7d32", "#1976d2", "#00838f", "#6a1b9a", "#c2185b", "#b45309", "#5d4037"];
    let hash = 0;
    for (let i = 0; i < n.length; i++) hash = ((hash << 5) - hash + n.charCodeAt(i)) | 0;
    return palette[Math.abs(hash) % palette.length];
  }

  _findDeep(root, selector) {
    if (!root) return null;
    if (root.matches?.(selector)) return root;
    const direct = root.querySelector?.(selector);
    if (direct) return direct;
    const children = root.querySelectorAll?.("*") || [];
    for (const el of children) {
      if (el.shadowRoot) {
        const found = this._findDeep(el.shadowRoot, selector);
        if (found) return found;
      }
    }
    if (root.shadowRoot) return this._findDeep(root.shadowRoot, selector);
    return null;
  }

  _parseTimeRange(text) {
    const m = String(text || "").match(/(?:^|\s)(\d{1,2}):(\d{2})\s*[–—-]\s*(\d{1,2}):(\d{2})(?:\s|$)/);
    if (!m) return null;
    const sh = Number(m[1]), sm = Number(m[2]), eh = Number(m[3]), em = Number(m[4]);
    if (![sh, sm, eh, em].every(Number.isFinite)) return null;
    if (sh > 23 || eh > 23 || sm > 59 || em > 59) return null;
    return {
      start: sh * 60 + sm,
      end: eh * 60 + em,
      startText: `${String(sh).padStart(2, "0")}:${String(sm).padStart(2, "0")}`,
      endText: `${String(eh).padStart(2, "0")}:${String(em).padStart(2, "0")}`,
    };
  }

  _shortCode(text) {
    const value = String(text || "").trim();
    if (!value) return "";
    const range = this._parseTimeRange(value);
    if (range) {
      return value.replace(/\s+\d{1,2}:\d{2}\s*[–—-]\s*\d{1,2}:\d{2}.*$/, "").trim().split(/\s+/)[0] || value.split(/\s+/)[0];
    }
    return value.split(/\s+/)[0];
  }

  _dayKey(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (!Number.isFinite(date?.getTime?.())) return "";
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  }

  _offsetDayKey(value, delta) {
    const date = value instanceof Date ? new Date(value.getTime()) : new Date(value);
    if (!Number.isFinite(date?.getTime?.())) return "";
    date.setDate(date.getDate() + delta);
    return this._dayKey(date);
  }

  _previousOvernightEvent(fc, entityId, day) {
    if (!fc || !entityId || !(day instanceof Date)) return null;
    const previousKey = this._offsetDayKey(day, -1);
    try {
      return (fc.getEvents?.() || []).find((event) => {
        if (event.extendedProps?.castncasaCarry === true) return false;
        if (event.extendedProps?.calendar !== entityId) return false;
        if (this._dayKey(event.start) !== previousKey) return false;
        const range = this._parseTimeRange(event.title);
        return !!range && range.end <= range.start;
      }) || null;
    } catch (_) {
      return null;
    }
  }

  _syncOvernightCarries(fc) {
    if (!fc || typeof fc.getEvents !== "function" || typeof fc.addEvent !== "function") return false;
    const residentIds = new Set(this._residentInfo.map((item) => item.id));
    const events = fc.getEvents();
    const regular = events.filter((event) => residentIds.has(event.extendedProps?.calendar) && event.extendedProps?.castncasaCarry !== true);
    const occupied = new Set(regular.map((event) => `${event.extendedProps?.calendar}|${this._dayKey(event.start)}`));
    const desired = new Map();

    regular.forEach((event) => {
      const range = this._parseTimeRange(event.title);
      if (!range || range.end > range.start) return;
      const entityId = event.extendedProps?.calendar;
      const originKey = this._dayKey(event.start);
      const nextKey = this._offsetDayKey(event.start, 1);
      if (!entityId || !originKey || !nextKey || occupied.has(`${entityId}|${nextKey}`)) return;
      const id = `castncasa-carry:${entityId}:${nextKey}`;
      desired.set(id, {
        id,
        title: event.title,
        start: nextKey,
        end: this._offsetDayKey(event.start, 2),
        allDay: true,
        backgroundColor: event.backgroundColor || event.borderColor || "#607d8b",
        borderColor: event.borderColor || event.backgroundColor || "#607d8b",
        extendedProps: {
          calendar: entityId,
          castncasaCarry: true,
          castncasaCarryOrigin: originKey,
        },
      });
    });

    let changed = false;
    events.filter((event) => event.extendedProps?.castncasaCarry === true).forEach((event) => {
      if (!desired.has(event.id)) {
        event.remove();
        changed = true;
      } else {
        desired.delete(event.id);
      }
    });
    desired.forEach((event) => {
      fc.addEvent(event);
      changed = true;
    });
    return changed;
  }

  _addSegment(el, leftPct, widthPct, color, label) {
    const segment = document.createElement("div");
    segment.className = "castncasa-timebar-segment";
    segment.style.position = "absolute";
    segment.style.left = `${leftPct}%`;
    segment.style.width = `${Math.max(0, widthPct)}%`;
    segment.style.top = "0";
    segment.style.bottom = "0";
    segment.style.background = color;
    segment.style.borderRadius = "7px";
    segment.style.overflow = "hidden";
    segment.style.display = "flex";
    segment.style.alignItems = "center";
    segment.style.justifyContent = "center";
    segment.style.padding = "0";
    segment.style.boxSizing = "border-box";
    segment.style.zIndex = "1";

    const text = document.createElement("span");
    text.textContent = label;
    text.style.color = "#fff";
    const isDesktop = window.matchMedia?.("(min-width: 1024px)")?.matches === true;
    text.style.fontWeight = isDesktop ? "800" : "700";
    text.style.lineHeight = "17px";
    text.style.whiteSpace = "nowrap";
    text.style.pointerEvents = "none";
    text.style.width = "100%";
    text.style.textAlign = "center";
    text.style.transformOrigin = "center center";

    if (widthPct < 10) {
      text.style.fontSize = isDesktop ? "12px" : "8px";
      text.style.transform = isDesktop ? "scaleX(.85)" : "scaleX(.55)";
    } else if (widthPct < 18) {
      text.style.fontSize = isDesktop ? "13px" : "9px";
      text.style.transform = isDesktop ? "none" : "scaleX(.75)";
    } else if (widthPct < 28) {
      text.style.fontSize = isDesktop ? "13px" : "10px";
      text.style.transform = isDesktop ? "none" : "scaleX(.9)";
    } else {
      text.style.fontSize = isDesktop ? "14px" : "11px";
      text.style.transform = "none";
    }

    segment.appendChild(text);
    el.appendChild(segment);
  }

  _styleMonthEvent(info) {
    if (!info?.el || !info?.event) return;

    const el = info.el;
    const props = info.event.extendedProps || {};
    const entityId = props.calendar || "";
    const isResident = this._residentInfo.some((item) => item.id === entityId);
    const isCarry = props.castncasaCarry === true;
    const color = info.event.backgroundColor || info.event.borderColor || "#607d8b";

    el.style.setProperty("border-radius", "7px", "important");

    if (!isResident) return;

    const label = this._shortCode(info.event.title);
    const range = this._parseTimeRange(info.event.title);

    el.querySelectorAll(".castncasa-timebar-segment").forEach((node) => node.remove());
    el.classList.add("castncasa-timebar");
    el.style.setProperty("position", "relative", "important");
    el.style.setProperty("border-color", "transparent", "important");
    el.style.setProperty("box-shadow", "none", "important");
    el.style.setProperty("background", "transparent", "important");
    el.style.setProperty("overflow", "visible", "important");
    el.style.setProperty("min-height", "17px", "important");

    const frame = el.querySelector(".fc-event-main-frame");
    if (frame) frame.style.setProperty("display", "none", "important");
    const main = el.querySelector(".fc-event-main");
    if (main) main.style.setProperty("background", "transparent", "important");

    if (!range) {
      this._addSegment(el, 0, 100, color, label);
      return;
    }

    const startPct = (range.start / 1440) * 100;
    const endPct = (range.end / 1440) * 100;

    if (isCarry) {
      this._addSegment(el, 0, endPct, color, label);
      return;
    }

    const previous = this._previousOvernightEvent(this._hookedCalendar, entityId, info.event.start);
    if (previous) {
      const previousRange = this._parseTimeRange(previous.title);
      if (previousRange) {
        const previousColor = previous.backgroundColor || previous.borderColor || color;
        this._addSegment(el, 0, (previousRange.end / 1440) * 100, previousColor, this._shortCode(previous.title));
      }
    }

    const overnight = range.end <= range.start;
    if (!overnight) {
      this._addSegment(el, startPct, endPct - startPct, color, label);
    } else {
      this._addSegment(el, startPct, 100 - startPct, color, label);
    }
  }

  _visibleMonthBounds(fc) {
    const anchor = typeof fc.getDate === "function" ? fc.getDate() : fc.view?.currentStart;
    if (!(anchor instanceof Date) || !Number.isFinite(anchor.getTime())) return null;
    const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1);
    return { start: start.getTime(), end: end.getTime() };
  }

  _updateLegend(fc, colors) {
    const entries = new Map();
    this._residentInfo.forEach((item) => entries.set(item.id, new Map()));
    const monthBounds = this._visibleMonthBounds(fc);

    try {
      for (const event of fc.getEvents?.() || []) {
        if (event.extendedProps?.castncasaCarry === true) continue;
        const entityId = event.extendedProps?.calendar;
        if (!entries.has(entityId)) continue;

        const eventStart = event.start?.getTime?.();
        if (monthBounds && Number.isFinite(eventStart)) {
          if (eventStart < monthBounds.start || eventStart >= monthBounds.end) continue;
        }

        const range = this._parseTimeRange(event.title);
        const code = this._shortCode(event.title);
        if (!code) continue;
        const display = range ? `${code} ${range.startText}–${range.endText}` : code;
        entries.get(entityId).set(display, display);
      }
    } catch (_) {}

    this.querySelectorAll(".castncasa-resident-block").forEach((block) => {
      const entityId = block.dataset.entity;
      const item = this._residentInfo.find((x) => x.id === entityId);
      const chip = block.querySelector(".castncasa-resident-chip");
      if (chip) {
        chip.style.background = colors.get(entityId) || this._fallbackColor(item?.name || "");
        chip.style.color = "#fff";
      }

      const list = block.querySelector(".castncasa-shift-list");
      if (!list) return;
      list.replaceChildren();
      const values = Array.from(entries.get(entityId)?.values() || []).sort((a, b) => a.localeCompare(b, "de"));
      values.forEach((value) => {
        const row = document.createElement("div");
        row.className = "castncasa-shift-entry";
        row.textContent = value;
        list.appendChild(row);
      });
    });
  }

  _scheduleTune() {
    [0, 80, 250, 700, 1400].forEach((delay) => {
      window.setTimeout(() => this._tuneCalendar(), delay);
    });
  }

  _tuneCalendar() {
    if (!this._card) return;
    const full = this._findDeep(this._card, "ha-full-calendar");
    const fc = full?.calendar;
    if (!fc || typeof fc.setOption !== "function") return;

    const isMonth = (this.config.initial_view || "dayGridMonth") === "dayGridMonth";
    if (isMonth) {
      fc.setOption("dayMaxEventRows", 4);
      if (this._hookedCalendar !== fc) {
        this._hookedCalendar = fc;
        fc.setOption("eventDidMount", (info) => this._styleMonthEvent(info));
        fc.setOption("datesSet", () => window.setTimeout(() => this._tuneCalendar(), 0));
        fc.setOption("eventsSet", () => window.setTimeout(() => this._tuneCalendar(), 0));
        if (typeof fc.rerenderEvents === "function") fc.rerenderEvents();
      }
      this._syncOvernightCarries(fc);
      fc.updateSize?.();
    }

    const colors = new Map();
    try {
      for (const event of fc.getEvents?.() || []) {
        const entityId = event.extendedProps?.calendar;
        const color = event.backgroundColor || event.borderColor;
        if (entityId && color && !colors.has(entityId)) colors.set(entityId, color);
      }
    } catch (_) {}

    this._updateLegend(fc, colors);

    if (this._card.style.visibility === "hidden") {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          if (this._card) this._card.style.visibility = "visible";
        });
      });
    }
  }

  getCardSize() { return 7; }
}

if (!customElements.get("castncasa-time-calendar")) {
  customElements.define("castncasa-time-calendar", CastnCasaTimeCalendar);
}
window.customCards = window.customCards || [];
window.customCards.push({
  type: "castncasa-time-calendar",
  name: "CastnCasa Zeitbalken",
  description: "Monatskalender mit zeitproportional positionierten Balken aus den echten Schichtzeiten."
});
