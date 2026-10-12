/* berse Offers card. Supplier content is always inserted as text. */
(() => {
  const CARD_TYPE = "berse-offers";

  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };

  const safeExternalUrl = (value) => {
    if (!value) return null;
    try {
      const url = new URL(value, window.location.origin);
      return url.protocol === "https:" ? url.href : null;
    } catch (_error) {
      return null;
    }
  };

  class BerseOffersEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
    }

    set hass(value) {
      this._hass = value;
      this._render();
    }

    setConfig(config) {
      this._config = { ...config };
      this._render();
    }

    _render() {
      if (!this.shadowRoot || !this._hass) return;
      const form = document.createElement("ha-form");
      form.hass = this._hass;
      form.data = { entity: this._config.entity || "" };
      form.schema = [
        {
          name: "entity",
          required: true,
          selector: { entity: { domain: ["sensor"] } },
        },
      ];
      form.computeLabel = (schema) => (schema.name === "entity" ? "Best offers sensor" : undefined);
      form.addEventListener("value-changed", (event) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            bubbles: true,
            composed: true,
            detail: { config: { ...this._config, ...event.detail.value } },
          }),
        );
      });
      this.shadowRoot.replaceChildren(form);
    }
  }

  class BerseOffersCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
    }
    setConfig(config) {
      if (!config.entity) throw new Error("Select a Best offers sensor.");
      this._config = { ...config };
      this._render();
    }
    set hass(value) {
      const previous = this._hass?.states[this._config.entity];
      this._hass = value;
      if (previous !== value.states[this._config.entity] || !this.shadowRoot.firstChild) this._render();
    }
    static getConfigElement() { return document.createElement("berse-offers-editor"); }
    static getStubConfig(hass) {
      const entity = Object.keys(hass?.states || {}).find(id =>
        id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.offers));
      return { entity: entity || "sensor.berse_best_offers" };
    }
    getCardSize() { return 9; }
    getGridOptions() { return { columns: 12, rows: 9, min_columns: 6, min_rows: 4 }; }
    _number(value) {
      if (value === null || value === undefined || value === "") return null;
      const result = Number(value);
      return Number.isFinite(result) ? result : null;
    }
    _format(value) {
      const number = this._number(value);
      return number === null ? "—" : new Intl.NumberFormat("en-GB", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      }).format(Object.is(number, -0) ? 0 : number);
    }
    _money(value) { return `€${this._format(value)}`; }
    _row(offer, index, baseline, maximum) {
      const cost = this._number(offer.candidate_cost);
      const saving = Math.round((baseline - cost) * 100) / 100;
      const tone = saving > 0 ? "saving" : saving < 0 ? "extra" : "equal";
      const row = element("li", `offer ${tone}`);
      const top = element("div", "top");
      const identity = element("div", "identity");
      identity.append(element("span", "rank", index + 1));
      const names = element("div", "names");
      names.append(element("strong", "supplier", offer.supplier_name || offer.supplier_code || "Unknown supplier"));
      names.append(element("span", "offer-name", offer.offer_name || "Unnamed offer"));
      identity.append(names);
      top.append(identity, element("strong", "cost", this._money(cost)));
      row.append(top);
      const track = element("div", "track");
      track.setAttribute("aria-hidden", "true");
      const bar = element("div", "bar");
      bar.style.width = `${100 * cost / maximum}%`;
      const marker = element("div", "marker");
      marker.style.left = `${100 * baseline / maximum}%`;
      track.append(bar, marker);
      row.append(track);
      const meta = element("div", "meta");
      meta.append(element("span", "unit-prices", `${this._money(offer.energy_price)}/kWh · ${this._money(offer.standing_charge)}/day`));
      const badge = saving > 0 ? `Save ${this._money(saving)}` : saving < 0
        ? `Costs ${this._money(Math.abs(saving))} more` : `No saving · ${this._money(0)}`;
      meta.append(element("span", `badge ${tone}`, badge));
      row.append(meta);
      const details = element("details");
      details.append(element("summary", "", "Offer details"));
      details.append(element("p", "muted", `Offer ${offer.offer_id || "—"} · ${offer.indexed ? "Indexed estimate" : "Fixed-price offer"} · ${offer.market || "Market not supplied"}`));
      if (offer.eligibility && typeof offer.eligibility === "object") {
        const conditions = Object.entries(offer.eligibility)
          .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
          .map(([key, value]) => `${key}: ${value}`);
        if (conditions.length) details.append(element("p", "muted", `Eligibility: ${conditions.join(" · ")}`));
      } else if (offer.eligibility) {
        details.append(element("p", "muted", `Eligibility: ${offer.eligibility}`));
      }
      if (offer.conditional_eligibility) details.append(element("p", "muted", "Conditional eligibility: check the supplier's requirements."));
      details.append(element("p", "muted", `Valid from ${offer.valid_from || "—"} to ${offer.valid_until || "—"}`));
      for (const [key, label] of [["offer_url", "Supplier offer"], ["terms_url", "Terms and conditions"]]) {
        const url = safeExternalUrl(offer[key]);
        if (!url) continue;
        const link = element("a", "", label);
        link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
        details.append(link);
      }
      row.append(details);
      return row;
    }
    _render() {
      if (!this._hass || !this._config.entity) return;
      const state = this._hass.states[this._config.entity];
      const data = state?.attributes || {};
      const style = element("style");
      style.textContent = `
        :host { display:block; color:var(--primary-text-color,#172b35); }
        ha-card { overflow:hidden; }
        .content { padding:24px; }
        h2 { font-size:22px; line-height:1.3; margin:4px 0 8px; letter-spacing:-.4px; }
        .eyebrow { color:var(--secondary-text-color,#657981); font-size:11px; letter-spacing:2px; font-weight:700; text-transform:uppercase; }
        .muted,.offer-name,.unit-prices,footer { color:var(--secondary-text-color,#657981); }
        .reference { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; padding:14px 0; margin:10px 0 0; font-size:13px; border-bottom:1px solid var(--divider-color,#ddd); }
        .reference strong { color:var(--primary-text-color); }
        .legend { display:flex; align-items:center; gap:7px; }
        .legend::before { content:""; height:16px; border-left:2px dashed var(--secondary-text-color,#657981); }
        ol { list-style:none; padding:0; margin:0; }
        .offer { padding:18px 0 14px; border-bottom:1px solid var(--divider-color,#ddd); }
        .top,.identity,.meta { display:flex; align-items:center; gap:12px; }
        .top,.meta { justify-content:space-between; }
        .identity { min-width:0; }
        .names { min-width:0; display:grid; gap:3px; }
        .supplier { font-size:15px; }
        .offer-name { font-size:12px; overflow-wrap:anywhere; }
        .rank { display:grid; place-items:center; background:var(--secondary-background-color,#edf3f5); border-radius:50%; width:25px; height:25px; flex-shrink:0; font-size:12px; }
        .cost { font-size:20px; white-space:nowrap; font-variant-numeric:tabular-nums; }
        .track { margin:14px 0 10px; position:relative; height:13px; border-radius:5px; background:var(--secondary-background-color,#edf3f5); }
        .bar { height:100%; border-radius:5px; background:var(--success-color,#168467); }
        .extra .bar { background:var(--error-color,#db4545); }
        .equal .bar { background:var(--secondary-text-color,#788d9a); }
        .marker { position:absolute; top:-6px; bottom:-6px; border-left:2px dashed var(--primary-text-color,#172b35); }
        .meta { flex-wrap:wrap; gap:7px; font-size:12px; }
        .badge { font-weight:600; }
        .saving.badge { color:var(--success-color,#168467); }
        .extra.badge,.extra .cost { color:var(--error-color,#db4545); }
        details { margin-top:10px; font-size:12px; }
        summary { cursor:pointer; color:var(--secondary-text-color,#657981); }
        details p { margin:8px 0; white-space:pre-wrap; }
        a { color:var(--primary-color,#007f99); display:inline-block; margin:4px 16px 0 0; }
        footer { font-size:11px; line-height:1.7; margin-top:14px; }
        button { cursor:pointer; margin-top:10px; padding:8px 12px; border:1px solid var(--divider-color,#ddd); border-radius:8px; background:transparent; color:var(--primary-text-color); font:inherit; }
        button:disabled { opacity:.6; }
        .notice { font-size:13px; padding:12px; background:var(--secondary-background-color,#edf3f5); border-radius:8px; line-height:1.5; }
        @media(max-width:420px) { .content { padding:16px; } .cost { font-size:18px; } .top { gap:8px; } .identity { gap:8px; } }
      `;
      const card = element("ha-card");
      const content = element("div", "content");
      content.append(element("div", "eyebrow", "berse · electricity comparison"));
      content.append(element("h2", "", this._config.title || "Your 5 best offers"));
      const source = data.reference_consumption_source === "manual" ? "Manual estimate" : data.reference_label || "Consumption reference";
      content.append(element("div", "muted", `${source} · ${this._format(data.reference_kwh)} kWh · ${data.reference_days ?? "—"} days`));
      const statuses = {
        unavailable: "The offers sensor is unavailable. Check the integration and the selected entity.",
        unknown: "Waiting for the first comparison.",
        insufficient_consumption: "Not enough consumption history. Choose manual consumption in the integration options to compare an estimate.",
        billing_not_started: "The configured billing period has not started.",
        no_matching_offers: "No eligible offers match your power and filters.",
      };
      const status = !state ? "unavailable" : ["unavailable", "unknown"].includes(state.state) ? state.state : data.ranking_status;
      if (statuses[status]) content.append(element("p", "notice", statuses[status]));
      if (data.status === "stale") content.append(element("p", "notice", "Catalog refresh failed. Showing the last successful catalog; prices may be outdated."));
      const offers = (Array.isArray(data.offers) ? data.offers : [])
        .filter(offer => offer && this._number(offer.candidate_cost) !== null && Number(offer.candidate_cost) >= 0)
        .sort((a,b) => Number(a.candidate_cost) - Number(b.candidate_cost)).slice(0,5);
      const baseline = offers.length ? this._number(offers[0].current_cost) : null;
      if (offers.length && baseline !== null && baseline >= 0) {
        const maximum = Math.max(baseline, ...offers.map(o => Number(o.candidate_cost)), 0.01) * 1.12;
        const reference = element("div", "reference");
        reference.append(element("span", "", `${this._format(data.power_kva)} kVA · excluding VAT`));
        reference.append(element("strong", "legend", `Your contract ${this._money(baseline)}`));
        content.append(reference);
        const list = element("ol");
        offers.forEach((offer,index) => list.append(this._row(offer,index,baseline,maximum)));
        content.append(list);
        if (offers.length < 5) content.append(element("p", "muted", `Only ${offers.length} eligible offers are available.`));
      } else if (!statuses[status]) {
        content.append(element("p", "notice", "No comparable offer costs are available yet."));
      }
      const footer = element("footer");
      footer.append(element("div", "", "Estimated energy + standing charge for the reference period. Taxes and additional charges are not included."));
      const date = new Date(data.last_successful_update || "");
      const timestamp = Number.isNaN(date.getTime()) ? "Not yet updated" : new Intl.DateTimeFormat("en-GB", {
        dateStyle:"medium", timeStyle:"short", timeZone:this._hass.config?.time_zone,
      }).format(date);
      footer.append(element("div", "", `Last update: ${timestamp}`));
      if (data.refresh_entity && this._hass.states[data.refresh_entity]) {
        const button = element("button", "", "Refresh offers");
        button.addEventListener("click", async () => {
          button.disabled = true;
          try { await this._hass.callService("button","press",{entity_id:data.refresh_entity}); }
          catch (_) { footer.append(element("p", "notice", "Refresh failed. Check Home Assistant and try again.")); }
          finally { button.disabled = false; }
        });
        footer.append(button);
      }
      content.append(footer); card.append(content);
      this.shadowRoot.replaceChildren(style,card);
    }
  }
  if (!customElements.get("berse-offers-editor")) customElements.define("berse-offers-editor", BerseOffersEditor);
  if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, BerseOffersCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some(card => card.type === CARD_TYPE)) window.customCards.push({
    type:CARD_TYPE, name:"berse Offers", preview:true,
    description:"Compare your five best electricity offers with cost bars and savings.",
  });
})();
