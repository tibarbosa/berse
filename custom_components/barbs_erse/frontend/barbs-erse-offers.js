/* barbs-erse Offers card. Supplier content is always inserted as text. */
(() => {
  const CARD_TYPE = "barbs-erse-offers";

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

  class BarbsErseOffersEditor extends HTMLElement {
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

  class BarbsErseOffersCard extends HTMLElement {
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
      if (!config.entity) throw new Error("Select a Best offers sensor.");
      this._config = { ...config };
      this._render();
    }

    static getConfigElement() {
      return document.createElement("barbs-erse-offers-editor");
    }

    static getStubConfig() {
      return { entity: "sensor.barbs_erse_best_offers" };
    }

    getCardSize() {
      return 4;
    }

    _formatPrice(value, unit) {
      const amount = Number(value);
      if (!Number.isFinite(amount)) return `${value} ${unit}`;
      const language = this._hass?.locale?.language || undefined;
      const formatted = new Intl.NumberFormat(language, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 10,
      }).format(amount);
      return `${formatted} ${unit}`;
    }

    _formatTime(value) {
      if (!value) return "Not available";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return new Intl.DateTimeFormat(this._hass?.locale?.language || undefined, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: this._hass?.config?.time_zone || undefined,
      }).format(date);
    }

    _statusText(attrs) {
      const status = attrs.ranking_status || attrs.status;
      if (status === "billing_not_started") return "Billing has not started.";
      if (status === "insufficient_consumption") return "Not enough consumption data.";
      if (status === "no_matching_offers") return "No matching offers.";
      if (status === "unavailable") return "No validated ERSE catalog is available.";
      if (status === "stale") return "Catalog refresh failed. Showing the last successful data.";
      return attrs.summary || "Offers are being prepared.";
    }

    _renderOffer(offer) {
      const item = element("li", "offer");
      const primary = element("div", "primary");
      primary.append(element("span", "supplier", offer.supplier_name || offer.supplier_code || "Unknown supplier"));
      primary.append(
        element(
          "span",
          "prices",
          `${this._formatPrice(offer.standing_charge, "€/day")} / ${this._formatPrice(offer.energy_price, "€/kWh")}`,
        ),
      );
      item.append(primary);
      const details = element("details", "details");
      details.append(element("summary", "details-summary", offer.offer_name || offer.offer_id || "Offer details"));
      const detailList = element("dl", "detail-list");
      const fields = [
        ["Supplier", offer.supplier_name || offer.supplier_code],
        ["Offer", offer.offer_name || offer.offer_id],
        ["Combined cost", this._formatPrice(offer.candidate_cost, "EUR")],
        ["Potential saving", this._formatPrice(offer.savings, "EUR")],
        ["Reference", offer.reference_label],
        ["Indexation", offer.indexed ? "Indexed estimate" : "Not indexed"],
        ["Validity", `${offer.valid_from || "Unknown"} – ${offer.valid_until || "Unknown"}`],
      ];
      for (const [label, value] of fields) {
        if (!value) continue;
        detailList.append(element("dt", "", label));
        detailList.append(element("dd", "", value));
      }
      if (offer.eligibility && Object.keys(offer.eligibility).length) {
        detailList.append(element("dt", "", "Conditions"));
        detailList.append(element("dd", "", Object.values(offer.eligibility).join(" · ")));
      }
      details.append(detailList);
      for (const [label, href] of [["Offer details", offer.offer_url], ["Terms", offer.terms_url]]) {
        const safeUrl = safeExternalUrl(href);
        if (!safeUrl) continue;
        const link = element("a", "offer-link", label);
        link.href = safeUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        details.append(link);
      }
      item.append(details);
      return item;
    }

    _render() {
      if (!this.shadowRoot || !this._hass) return;
      const style = element("style");
      style.textContent = `
        :host { display: block; }
        ha-card { padding: 16px; }
        header { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
        h2 { font-size: 1.15rem; margin: 0; }
        .subtitle, .meta, .status { color: var(--secondary-text-color); font-size: .9rem; }
        .subtitle { margin-top: 5px; }
        .meta { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 12px 0; }
        ul { list-style: none; margin: 0; padding: 0; }
        .offer { border-top: 1px solid var(--divider-color); padding: 11px 0; }
        .primary { display: flex; justify-content: space-between; gap: 12px; }
        .supplier { font-weight: 600; }
        .prices { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
        .details { margin-top: 5px; font-size: .85rem; }
        .details-summary { color: var(--secondary-text-color); cursor: pointer; }
        .detail-list { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; }
        dt { font-weight: 600; } dd { margin: 0; overflow-wrap: anywhere; }
        .offer-link { margin-right: 12px; }
        .footer { border-top: 1px solid var(--divider-color); padding-top: 10px; margin-top: 8px; }
        .refresh { border: 0; background: none; color: var(--primary-color); cursor: pointer; font: inherit; padding: 4px 0; }
        .status { margin: 12px 0; }
      `;
      const card = element("ha-card");
      const header = element("header");
      const heading = element("div");
      heading.append(element("h2", "", "barbs-erse · Best offers"));
      const state = this._hass.states[this._config.entity];
      if (!state) {
        heading.append(element("p", "status", "Loading offers…"));
        header.append(heading);
        card.append(header);
        this.shadowRoot.replaceChildren(style, card);
        return;
      }
      const attrs = state.attributes || {};
      const offers = Array.isArray(attrs.offers) ? attrs.offers : [];
      heading.append(
        element(
          "div",
          "subtitle",
          `${attrs.power_kva || "—"} kVA · Single rate · Excluding VAT`,
        ),
      );
      header.append(heading);
      card.append(header);
      if (attrs.status === "stale") card.append(element("p", "status", this._statusText(attrs)));
      if (attrs.status === "unavailable" || offers.length === 0) {
        card.append(element("p", "status", this._statusText(attrs)));
      }
      if (offers.length) {
        const list = element("ul");
        for (const offer of offers.slice(0, 10)) list.append(this._renderOffer(offer));
        card.append(list);
      }
      const footer = element("div", "footer");
      const meta = element("div", "meta");
      const lastUpdate = attrs.last_successful_update
        ? `Last update: ${this._formatTime(attrs.last_successful_update)}`
        : "Last update: not yet successful";
      meta.append(element("span", "", lastUpdate));
      meta.append(element("span", "", `New offers: ${attrs.new_offer_count ?? 0}`));
      if (attrs.reference_kwh !== null && attrs.reference_kwh !== undefined) {
        meta.append(element("span", "", `Ranking: ${attrs.reference_kwh} kWh over ${attrs.reference_days} days`));
      }
      footer.append(meta);
      if (attrs.refresh_entity) {
        const refresh = element("button", "refresh", "Refresh offers");
        refresh.type = "button";
        refresh.addEventListener("click", () => {
          this._hass.callService("button", "press", { entity_id: attrs.refresh_entity });
        });
        footer.append(refresh);
      }
      card.append(footer);
      this.shadowRoot.replaceChildren(style, card);
    }
  }

  if (!customElements.get("barbs-erse-offers-editor")) {
    customElements.define("barbs-erse-offers-editor", BarbsErseOffersEditor);
  }
  if (!customElements.get("barbs-erse-offers-card")) {
    customElements.define("barbs-erse-offers-card", BarbsErseOffersCard);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
    window.customCards.push({
      type: CARD_TYPE,
      name: "barbs-erse Offers",
      description: "Compare VAT-exclusive single-rate electricity offers from ERSE.",
      preview: false,
      documentationURL: "https://github.com/tibarbosa/ha-erse#offers-card",
    });
  }
})();
