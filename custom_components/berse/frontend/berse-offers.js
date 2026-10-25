/* berse Offers card. Supplier content is always inserted as text. */
(() => {
  const CARD_TYPE = "berse-offers";
  const MAX_OFFERS = 15;
  const DEFAULT_VISIBLE_OFFERS = 3;

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
      form.data = { entity: this._config.entity || "", show_supplier_logos: this._config.show_supplier_logos !== false };
      form.schema = [
        {
          name: "entity",
          required: true,
          selector: { entity: { domain: ["sensor"] } },
        },
      ];
      form.schema.push({ name: "show_supplier_logos", selector: { boolean: {} } });
      form.computeLabel = (schema) => ({
        entity: "Best offers sensor", show_supplier_logos: "Show supplier logos",
      })[schema.name];
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
      this._visibleOfferCount = DEFAULT_VISIBLE_OFFERS;
    }
    setConfig(config) {
      if (!config.entity) throw new Error("Select a Best offers sensor.");
      if (config.entity !== this._config.entity) this._visibleOfferCount = DEFAULT_VISIBLE_OFFERS;
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
    getCardSize() {
      return Math.ceil((this.shadowRoot.querySelector("ha-card")?.getBoundingClientRect().height || 750) / 50);
    }
    getGridOptions() { return { columns: 12, rows: "auto", min_columns: 6 }; }
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
    _unit(value) {
      const number = this._number(value);
      return number === null ? "Not provided" : new Intl.NumberFormat("en-GB", {
        minimumFractionDigits: 4, maximumFractionDigits: 4,
      }).format(number);
    }
    _flag(value) {
      const normalized = String(value ?? "").trim().toLowerCase();
      if (["s", "sim", "y", "yes", "true", "1"].includes(normalized)) return true;
      if (["n", "não", "nao", "no", "false", "0"].includes(normalized)) return false;
      return null;
    }
    _choices(value, labels) {
      const flags = String(value || "").trim();
      if (flags.length !== labels.length || !/^[01]+$/.test(flags) || !flags.includes("1")) return null;
      return labels.filter((_, index) => flags[index] === "1");
    }
    _conditions(offer) {
      const source = offer.eligibility || {};
      const tags = [];
      if (this._flag(source.FiltroNovosClientes) === true) tags.push("New-customer conditions");
      if (source.FiltroPagamento === "100") tags.push("Direct debit required");
      if (source.Filtrofaturacao === "10") tags.push("E-bill required");
      if (source.FiltroContratacao === "100") tags.push("Online sign-up only");
      if (this._flag(source["FiltroFidelização"]) === false) tags.push("No commitment indicated");
      if (this._flag(source["FiltroRestrições"]) === true) tags.push("Additional restrictions");
      if (this._flag(source.FiltroServicosAdic) === true) tags.push("Mandatory extra services");
      return tags;
    }
    _logo(offer) {
      const holder = element("span", "supplier-logo");
      const name = offer.supplier_name || offer.supplier_code || "?";
      const initials = String(name).split(/\s+/).filter(Boolean).map(part => part[0]).join("").slice(0, 3).toUpperCase();
      holder.append(element("span", "initials", initials));
      // Only local packaged or cached assets can be loaded; never remote image URLs.
      if (typeof offer.supplier_logo_url === "string" && /^\/berse\/(?:suppliers|supplier-cache)\/[a-z0-9_-]+\.(png|jpg)$/.test(offer.supplier_logo_url)) {
        const image = element("img");
        image.alt = ""; image.loading = "lazy"; image.decoding = "async";
        image.addEventListener("load", () => holder.classList.add("loaded"));
        image.addEventListener("error", () => { image.remove(); holder.classList.remove("loaded"); });
        image.src = offer.supplier_logo_url;
        holder.append(image);
      }
      holder.setAttribute("aria-hidden", "true");
      return holder;
    }
    _details(offer, kwh, days) {
      const details = element("details", "offer-details");
      details.dataset.identity = offer.identity || offer.offer_id;
      details.append(element("summary", "", "Offer details"));
      const source = offer.eligibility && typeof offer.eligibility === "object" ? offer.eligibility : {};
      const commercial = offer.commercial_details || {};
      const grid = element("div", "details-grid");
      const group = (heading, lines) => {
        const section = element("section");
        section.append(element("h3", "", heading));
        lines.forEach(line => section.append(element("p", "muted", line)));
        grid.append(section);
      };
      const yesNo = (value, yes, no) => {
        const flag = this._flag(value);
        return flag === null ? "Not provided" : flag ? yes : no;
      };
      const choices = (value, labels) => this._choices(value, labels)?.join(" · ") || "Not provided";
      group("Eligibility", [
        `Sign-up: ${choices(source.FiltroContratacao, ["Online", "In person", "By phone"])}`,
        `New customers: ${yesNo(source.FiltroNovosClientes, "Benefits or conditions apply; check eligibility", "No new-customer benefit flagged")}`,
        `Additional restrictions: ${yesNo(source["FiltroRestrições"], "Apply; check original information", "None flagged")}`,
      ]);
      const duration = String(commercial.DuracaoContrato || "").trim();
      group("Contract and promotion", [
        `Contract duration: ${/^\d+(?:[.,]\d+)?$/.test(duration) ? `${duration.replace(",", ".")} months` : "Not provided"}`,
        `Commitment: ${yesNo(source["FiltroFidelização"], "Commitment indicated; check supplier terms", "No commitment indicated")}`,
        "Promotion and renewal: check the original information and supplier documents. Contract duration, discount duration and offer validity can differ.",
      ]);
      const precise = (value) => this._unit(value);
      group("Price breakdown", [
        `Energy: €${precise(offer.energy_price)}/kWh${kwh === null ? "" : ` · ${this._money(kwh * Number(offer.energy_price))}`}`,
        `Standing charge: €${precise(offer.standing_charge)}/day${days === null ? "" : ` · ${this._money(days * Number(offer.standing_charge))}`}`,
        "Excluding VAT. Source unit rates are used as published; no additional promotional refund or social-tariff discount is deducted. Rounded components may not sum exactly.",
      ]);
      group("Billing and payment", [
        `Invoices: ${choices(source.Filtrofaturacao, ["Electronic", "Paper"])}`,
        `Payment: ${choices(source.FiltroPagamento, ["Direct debit", "Multibanco", "Cash / Payshop / CTT"])}`,
        `Support: ${choices(source.FiltroAtendimento, ["Written", "In person", "By phone", "Digital"])}`,
        `Billing interval: ${commercial.TxTFaturacao ? "See original ERSE information" : "Not provided"}`,
      ]);
      group("Price updates", [
        offer.indexed === true ? "Indexed estimate" : offer.indexed === false ? "Non-indexed offer" : "Indexation: Not provided",
        commercial.TxTAtualizaPrecos ? "Price revision rules are supplied; see original ERSE information." : "Price revision rules: Not provided",
        "Non-indexed does not guarantee unchanged prices. Check the supplier's revision terms.",
      ]);
      group("Other conditions", [
        `Renewable electricity: ${yesNo(source.FiltroRenovavel_ELE, "100% according to the source", "Not flagged as 100% renewable")}`,
        `Mandatory extra services: ${yesNo(source.FiltroServicosAdic, "Required; check costs and terms", "None flagged")}`,
        ...(this._flag(source.FiltroServicosAdic) === true ? [`Published annual service cost: ${this._money(offer.mandatory_services_per_year)} excluding VAT. Not included in energy + standing-charge bars.`] : []),
        `Social tariff: ${yesNo(source.FiltroTarifaSocial, "Available to eligible households; not applied here", "Not flagged")}`,
        `Offer validity: ${offer.valid_from || "Not provided"} – ${offer.valid_until || "Not provided"}`,
      ]);
      details.append(grid);
      if (offer.conditional_eligibility) details.append(element("p", "notice", "Conditional eligibility: check the supplier's requirements before switching."));
      const original = element("details", "original");
      original.append(element("summary", "", "Original ERSE information"));
      const fields = {
        TxTOferta: "Offer and promotion", TxTERSE: "ERSE notes", "TxTContratação": "Sign-up",
        TxTFatura: "Invoice", TxTPagamento: "Payment", "TxTFidelização": "Commitment",
        TxTRestricoesAdic: "Additional restrictions", "Detalhe restrições": "Restriction details",
        TxTServicoAdic: "Mandatory services", DuracaoContrato: "Contract duration (months)",
        TxTFaturacao: "Billing interval", TxTAtendimento: "Customer support",
        TxTAtualizaPrecos: "Price updates", TxToutrosServicoAdic: "Other services",
        TxTReembolsos: "Refunds and promotions", "DetalheOutrosDesc/benefi": "Other benefits",
      };
      const seen = new Set();
      for (const [key, label] of Object.entries(fields)) {
        const value = String(commercial[key] || source[key] || "").trim();
        if (!value || seen.has(value)) continue;
        seen.add(value);
        original.append(element("h3", "", label));
        const paragraph = element("p", "muted", value);
        paragraph.lang = "pt";
        original.append(paragraph);
      }
      if (!seen.size) original.append(element("p", "muted", "Not provided"));
      details.append(original);
      const links = element("div", "offer-links");
      for (const [key, label] of [["offer_url", "Offer page"], ["terms_url", "Offer factsheet"], ["general_conditions_url", "General conditions"]]) {
        const url = safeExternalUrl(offer[key]);
        if (!url) continue;
        const link = element("a", "", label);
        link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
        links.append(link);
      }
      details.append(links, element("p", "muted", `Source offer ID: ${offer.offer_id || "Not provided"}`));
      return details;
    }
    _row(offer, index, baseline, maximum, kwh, days) {
      const cost = this._number(offer.candidate_cost);
      const saving = Math.round((baseline - cost) * 100) / 100;
      const tone = saving > 0 ? "saving" : saving < 0 ? "extra" : "equal";
      const row = element("li", `offer ${tone}`);
      const top = element("div", "top");
      const identity = element("div", "identity");
      identity.append(element("span", "rank", index + 1));
      if (this._config.show_supplier_logos !== false) identity.append(this._logo(offer));
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
      meta.append(element("span", "unit-prices", `€${this._unit(offer.energy_price)}/kWh · €${this._unit(offer.standing_charge)}/day`));
      const badge = saving > 0 ? `Save ${this._money(saving)}${saving < 1 ? " · Marginal saving" : ""}` : saving < 0
        ? `Costs ${this._money(Math.abs(saving))} more` : `No saving · ${this._money(0)}`;
      meta.append(element("span", `badge ${tone}`, badge));
      row.append(meta);
      const tags = element("div", "conditions");
      this._conditions(offer).forEach(label => tags.append(element("span", "condition", label)));
      if (tags.childNodes.length) row.append(tags);
      row.append(this._details(offer, kwh, days));
      return row;
    }
    _offerControls(list, total) {
      const controls = element("div", "offer-controls");
      const status = element("span", "muted");
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      const actions = element("div", "offer-control-actions");
      const label = element("label", "offer-count-label", "Show");
      const select = element("select", "offer-count");
      select.setAttribute("aria-label", "Number of offers to show");
      select.setAttribute("aria-controls", list.id);
      const choices = [...new Set([3, 6, 9, 12, MAX_OFFERS].map(count => Math.min(count, total)))];
      for (const count of choices) {
        const option = element("option", "", `${count} offers`);
        option.value = String(count);
        select.append(option);
      }
      label.append(select);
      const toggle = element("button", "offer-expansion");
      toggle.type = "button";
      toggle.setAttribute("aria-controls", list.id);
      actions.append(label, toggle);
      actions.hidden = total <= DEFAULT_VISIBLE_OFFERS;
      controls.append(status, actions);
      const update = () => {
        const visible = Math.min(this._visibleOfferCount, total);
        [...list.children].forEach((row, index) => { row.hidden = index >= visible; });
        status.textContent = `Showing ${visible} of ${total} offers`;
        select.value = String(visible);
        toggle.textContent = visible === total ? "Show top 3" : `Show all ${total} offers`;
        toggle.setAttribute("aria-expanded", String(visible > DEFAULT_VISIBLE_OFFERS));
      };
      select.addEventListener("change", () => {
        const selected = Number(select.value);
        this._visibleOfferCount = selected === total ? MAX_OFFERS : selected;
        update();
      });
      toggle.addEventListener("click", () => {
        this._visibleOfferCount = this._visibleOfferCount >= total ? DEFAULT_VISIBLE_OFFERS : MAX_OFFERS;
        update();
      });
      update();
      return controls;
    }
    _render() {
      if (!this._hass || !this._config.entity) return;
      const state = this._hass.states[this._config.entity];
      const data = state?.attributes || {};
      const expanded = new Set([...this.shadowRoot.querySelectorAll("details.offer-details[open]")].map(node => node.dataset.identity));
      const originalExpanded = new Set([...this.shadowRoot.querySelectorAll("details.offer-details")].filter(node => node.querySelector(".original")?.open).map(node => node.dataset.identity));
      const style = element("style");
      style.textContent = `
        :host { display:block; color:var(--primary-text-color,#172b35); }
        ha-card { overflow:hidden; }
        [hidden] { display:none !important; }
        .offer-controls { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; padding:18px 0 4px; }
        .offer-control-actions,.offer-count-label { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .offer-count-label { color:var(--secondary-text-color,#657981); font-size:12px; }
        .offer-controls button { margin-top:0; min-height:40px; font-size:13px; }
        .offer-count { font:inherit; font-size:13px; min-height:40px; padding:8px 10px; border:1px solid var(--divider-color,#ddd); border-radius:8px; color:var(--primary-text-color,#172b35); background:var(--secondary-background-color,#edf3f5); }
        @media(pointer:coarse) { .offer-controls button,.offer-count { min-height:44px; } }
        @media(max-width:420px) { .offer-control-actions { width:100%; justify-content:space-between; } .offer-count { font-size:16px; } }
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
        .track { margin:14px 0 10px; position:relative; height:8px; border-radius:5px; background:var(--secondary-background-color,#edf3f5); }
        .bar { height:100%; border-radius:5px; background:var(--success-color,#168467); }
        .extra .bar { background:var(--error-color,#db4545); }
        .equal .bar { background:var(--secondary-text-color,#788d9a); }
        .marker { position:absolute; top:-6px; bottom:-6px; border-left:2px dashed var(--primary-text-color,#172b35); }
        .meta { flex-wrap:wrap; gap:7px; font-size:12px; }
        .badge { font-weight:600; }
        .saving.badge { color:var(--success-color,#168467); }
        .extra.badge,.extra .cost { color:var(--error-color,#db4545); }
        .supplier-logo { width:40px; height:40px; flex-shrink:0; border-radius:8px; display:grid; place-items:center; position:relative; background:var(--secondary-background-color,#edf3f5); }
        .supplier-logo img { width:100%; height:100%; object-fit:contain; padding:4px; background:#fff; border-radius:8px; grid-area:1/1; opacity:0; }
        .supplier-logo.loaded img { opacity:1; }
        .initials { grid-area:1/1; font-size:12px; color:var(--secondary-text-color,#657981); }
        .supplier-logo.loaded .initials { visibility:hidden; }
        .conditions { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
        .condition { background:var(--secondary-background-color,#edf3f5); color:var(--secondary-text-color,#657981); border-radius:5px; padding:3px 7px; font-size:11px; }
        .common-conditions { color:var(--secondary-text-color,#657981); font-size:12px; margin:10px 0; }
        .details-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; padding:16px 0; }
        .details-grid section { min-width:0; }
        h3 { font-size:12px; margin:0 0 6px; font-weight:600; }
        details p { line-height:1.6; overflow-wrap:anywhere; }
        .original { border-top:1px solid var(--divider-color,#ddd); padding-top:8px; }
        .original h3 { margin-top:14px; }
        summary { min-height:32px; color:var(--primary-color,#007f99); }
        .offer-links { display:flex; flex-wrap:wrap; }
        @media(pointer:coarse) { summary { min-height:44px; } }
        @media(max-width:540px) { .details-grid { grid-template-columns:1fr; } }
        @media(max-width:360px) { .supplier-logo { width:30px; height:30px; } .rank { width:18px; height:18px; } .cost { font-size:16px; } }
        details { margin-top:10px; font-size:12px; }
        summary { cursor:pointer; }
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
      content.append(element("h2", "", this._config.title || "Your best offers"));
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
        .sort((a,b) => Number(a.candidate_cost) - Number(b.candidate_cost)).slice(0,MAX_OFFERS);
      const baseline = offers.length ? this._number(offers[0].current_cost) : null;
      if (offers.length && baseline !== null && baseline >= 0) {
        const maximum = Math.max(baseline, ...offers.map(o => Number(o.candidate_cost)), 0.01) * 1.12;
        const reference = element("div", "reference");
        reference.append(element("span", "", `${this._format(data.power_kva)} kVA · Single rate · excluding VAT`));
        reference.append(element("strong", "legend", `Your contract ${this._money(baseline)}`));
        content.append(reference);
        const common = this._conditions(offers[0]).filter(label => offers.every(offer => this._conditions(offer).includes(label)));
        if (offers.length > 1 && common.length) content.append(element("div", "common-conditions", `All ${offers.length} offers: ${common.join(" · ")}`));
        const list = element("ol");
        list.id = "berse-offers-list";
        offers.forEach((offer,index) => {
          const row = this._row(offer,index,baseline,maximum,this._number(data.reference_kwh),this._number(data.reference_days));
          const details = row.querySelector(".offer-details");
          details.open = expanded.has(details.dataset.identity);
          details.querySelector(".original").open = originalExpanded.has(details.dataset.identity);
          list.append(row);
        });
        content.append(list, this._offerControls(list, offers.length));
        if (offers.length < MAX_OFFERS) content.append(element("p", "muted", `Only ${offers.length} eligible offers are available.`));
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
    description:"Compare up to fifteen electricity offers, showing the best three first.",
  });
})();
