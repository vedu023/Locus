const DEFAULT_FIELDS = {
  sales: [
    "basic_info.name",
    "basic_info.primary_domain",
    "basic_info.website",
    "taxonomy.professional_network_industry",
    "headcount.total",
    "funding.total_investment_usd",
    "funding.last_round_type",
    "funding.last_fundraise_date",
    "locations.headquarters",
  ],
  recruiting: [
    "basic_profile.name",
    "basic_profile.headline",
    "basic_profile.location",
    "experience.employment_details.current.title",
    "experience.employment_details.current.company_name",
    "experience.employment_details.current.company_website_domain",
    "experience.employment_details.current.seniority_level",
    "experience.employment_details.current.function_category",
    "contact.has_business_email",
    "contact.has_phone_number",
    "social_handles.professional_network_identifier.profile_url",
  ],
  investor: [
    "basic_info.name",
    "basic_info.primary_domain",
    "basic_info.website",
    "basic_info.markets",
    "taxonomy.categories",
    "taxonomy.professional_network_industry",
    "headcount.total",
    "funding.total_investment_usd",
    "funding.last_round_type",
    "funding.last_fundraise_date",
    "followers.six_months_growth_percent",
    "hiring.openings_growth_percent",
    "roles.growth_6m",
    "locations.headquarters",
  ],
};

const STORAGE_KEYS = {
  lens: "locus.ui.lens",
  runId: "locus.ui.run",
  watchlistId: "locus.ui.watchlist",
};

const state = {
  lens: window.localStorage.getItem(STORAGE_KEYS.lens) || "sales",
  auth: null,
  liveStatus: "Unknown",
  adminMetrics: null,
  currentRun: null,
  summary: null,
  clusters: null,
  entities: null,
  watchlists: [],
  watchlistSignals: [],
  selectedWatchlistId: window.localStorage.getItem(STORAGE_KEYS.watchlistId),
  focusLocationId: null,
  selectedClusterId: null,
  entityFilter: "all",
  isBusy: false,
  message: "Launching a run will hydrate this shell from the backend state already in the database.",
};

const refs = {};

document.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => {
    console.error(error);
    setMessage(error.message || "Frontend initialization failed.");
  });
});

async function init() {
  cacheDom();
  bindEvents();
  applyLens(state.lens);
  renderAll();

  await Promise.all([
    loadAuthContext(),
    loadServiceHealth(),
    loadWatchlists({ quiet: true }),
    loadAdminMetrics(),
  ]);

  const initialRunId = new URL(window.location.href).searchParams.get("run")
    || window.localStorage.getItem(STORAGE_KEYS.runId);
  if (initialRunId) {
    await loadRun(initialRunId, { announce: false });
  } else {
    renderAll();
  }
}

function cacheDom() {
  refs.userBadge = document.querySelector("#userBadge");
  refs.liveStatus = document.querySelector("#liveStatus");
  refs.runBadge = document.querySelector("#runBadge");
  refs.runForm = document.querySelector("#runForm");
  refs.watchlistForm = document.querySelector("#watchlistForm");
  refs.heroTitle = document.querySelector("#heroTitle");
  refs.runMeta = document.querySelector("#runMeta");
  refs.statGrid = document.querySelector("#statGrid");
  refs.eventStrip = document.querySelector("#eventStrip");
  refs.mapSvg = document.querySelector("#mapSvg");
  refs.mapLegend = document.querySelector("#mapLegend");
  refs.clusterDetail = document.querySelector("#clusterDetail");
  refs.summaryBody = document.querySelector("#summaryBody");
  refs.entityList = document.querySelector("#entityList");
  refs.entityCountLabel = document.querySelector("#entityCountLabel");
  refs.watchlistList = document.querySelector("#watchlistList");
  refs.watchlistBadge = document.querySelector("#watchlistBadge");
  refs.signalTimeline = document.querySelector("#signalTimeline");
  refs.lensPills = [...document.querySelectorAll(".lens-pill")];
  refs.lensPanels = [...document.querySelectorAll("[data-lens-panel]")];
  refs.entityFilter = document.querySelector("#entityFilter");
  refs.runButton = document.querySelector("#runButton");
  refs.reloadRunButton = document.querySelector("#reloadRunButton");
  refs.refreshWatchlistButton = document.querySelector("#refreshWatchlistButton");
  refs.resetFocusButton = document.querySelector("#resetFocusButton");
}

function bindEvents() {
  refs.lensPills.forEach((button) => {
    button.addEventListener("click", () => applyLens(button.dataset.lens));
  });

  refs.runForm.addEventListener("submit", handleRunSubmit);
  refs.watchlistForm.addEventListener("submit", handleWatchlistCreate);
  refs.entityFilter.addEventListener("change", handleEntityFilterChange);
  refs.reloadRunButton.addEventListener("click", handleRunReload);
  refs.refreshWatchlistButton.addEventListener("click", handleWatchlistRefresh);
  refs.resetFocusButton.addEventListener("click", handleResetFocus);
  refs.summaryBody.addEventListener("click", handleActionClick);
  refs.entityList.addEventListener("click", handleActionClick);
  refs.watchlistList.addEventListener("click", handleActionClick);
  refs.mapSvg.addEventListener("click", handleMapClick);
}

function applyLens(lens) {
  state.lens = lens;
  window.localStorage.setItem(STORAGE_KEYS.lens, lens);
  refs.lensPills.forEach((button) => {
    button.classList.toggle("active", button.dataset.lens === lens);
  });
  refs.lensPanels.forEach((panel) => {
    const isActive = panel.dataset.lensPanel === lens;
    panel.hidden = !isActive;
    panel.classList.toggle("active", isActive);
  });
  setMessage(`Lens switched to ${titleCase(lens)}. Tune the search controls and launch a run.`);
  renderHeader();
}

async function handleRunSubmit(event) {
  event.preventDefault();
  const payload = buildRunPayload();
  setBusy(true);
  try {
    setMessage(`Launching ${titleCase(payload.lens)} run...`);
    const response = await requestJson("/api/runs", {
      method: "POST",
      body: payload,
    });
    await loadRun(response.run_id, { announce: true });
  } finally {
    setBusy(false);
  }
}

async function handleWatchlistCreate(event) {
  event.preventDefault();
  const name = refs.watchlistForm.elements.watchlistName.value.trim();
  if (!name) {
    setMessage("Watchlist name is required.");
    return;
  }

  const description = refs.watchlistForm.elements.watchlistDescription.value.trim();
  try {
    setMessage(`Creating watchlist ${name}...`);
    const watchlist = await requestJson("/api/watchlists", {
      method: "POST",
      body: {
        name,
        lens: state.lens,
        description: description || null,
      },
    });
    refs.watchlistForm.reset();
    state.selectedWatchlistId = watchlist.watchlist_id;
    window.localStorage.setItem(STORAGE_KEYS.watchlistId, watchlist.watchlist_id);
    await loadWatchlists();
    setMessage(`Watchlist ${name} is ready for tracked entities.`);
  } catch (error) {
    console.error(error);
  }
}

async function handleEntityFilterChange() {
  state.entityFilter = refs.entityFilter.value;
  if (!state.currentRun) {
    renderAll();
    return;
  }

  setBusy(true);
  try {
    await loadRunSlices(state.currentRun.run_id);
    setMessage(`Entity filter set to ${state.entityFilter}.`);
  } finally {
    setBusy(false);
  }
}

async function handleRunReload() {
  if (!state.currentRun) {
    setMessage("No run is loaded yet.");
    return;
  }

  setBusy(true);
  try {
    await loadRun(state.currentRun.run_id, { announce: true });
  } finally {
    setBusy(false);
  }
}

async function handleWatchlistRefresh() {
  if (!state.selectedWatchlistId) {
    setMessage("Select a watchlist before running refresh.");
    return;
  }

  try {
    const response = await requestJson(
      `/api/watchlists/${state.selectedWatchlistId}/refresh`,
      { method: "POST" },
    );
    await loadWatchlists();
    setMessage(
      `Watchlist refresh complete: ${response.refreshed_companies} companies, ${response.refreshed_people} people, ${response.signals_upserted} signals.`,
    );
  } catch (error) {
    console.error(error);
  }
}

async function handleResetFocus() {
  state.focusLocationId = null;
  state.selectedClusterId = null;
  if (state.currentRun) {
    setBusy(true);
    try {
      await loadRunSlices(state.currentRun.run_id);
      setMessage("Map focus cleared.");
    } finally {
      setBusy(false);
    }
    return;
  }
  renderMap();
}

function handleActionClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }

  const action = target.dataset.action;
  if (action === "watchlist-add") {
    addEntityToSelectedWatchlist(target.dataset.entityType, target.dataset.entityId);
    return;
  }
  if (action === "select-watchlist") {
    selectWatchlist(target.dataset.watchlistId);
    return;
  }
  if (action === "remove-watchlist-item") {
    removeWatchlistItem(target.dataset.watchlistId, target.dataset.itemId);
  }
}

function handleMapClick(event) {
  const target = event.target.closest("[data-cluster-id]");
  if (!target) {
    return;
  }
  const clusterId = target.dataset.clusterId;
  const cluster = state.clusters?.clusters?.find((item) => item.cluster_id === clusterId);
  if (!cluster) {
    return;
  }

  state.selectedClusterId = clusterId;
  const singleLocation = cluster.location_ids.length === 1 ? cluster.location_ids[0] : null;
  if (singleLocation) {
    state.focusLocationId = singleLocation;
    if (state.currentRun) {
      loadRunSlices(state.currentRun.run_id)
        .then(() => {
          setMessage(`Focused on ${cluster.labels[0] || "selected cluster"}.`);
        })
        .catch((error) => {
          console.error(error);
        });
      return;
    }
  }

  setMessage(`Selected cluster with ${cluster.entity_count} entities.`);
  renderMap();
}

async function addEntityToSelectedWatchlist(entityType, entityId) {
  if (!entityType || !entityId) {
    return;
  }
  if (!state.selectedWatchlistId) {
    setMessage("Create or select a watchlist before adding entities.");
    return;
  }

  const body = { entity_type: entityType };
  if (entityType === "company") {
    body.company_id = entityId;
  } else {
    body.person_id = entityId;
  }

  try {
    await requestJson(`/api/watchlists/${state.selectedWatchlistId}/items`, {
      method: "POST",
      body,
    });
    await loadWatchlists();
    setMessage(`Tracked ${entityType} added to the selected watchlist.`);
  } catch (error) {
    console.error(error);
  }
}

async function removeWatchlistItem(watchlistId, itemId) {
  if (!watchlistId || !itemId) {
    return;
  }

  try {
    await requestJson(`/api/watchlists/${watchlistId}/items/${itemId}`, {
      method: "DELETE",
    });
    await loadWatchlists();
    setMessage("Watchlist item removed.");
  } catch (error) {
    console.error(error);
  }
}

async function selectWatchlist(watchlistId) {
  state.selectedWatchlistId = watchlistId;
  if (watchlistId) {
    window.localStorage.setItem(STORAGE_KEYS.watchlistId, watchlistId);
    await loadWatchlistSignals(watchlistId);
  } else {
    window.localStorage.removeItem(STORAGE_KEYS.watchlistId);
    state.watchlistSignals = [];
  }
  renderWatchlists();
  renderSignals();
}

async function loadRun(runId, { announce = true } = {}) {
  const run = await requestJson(`/api/runs/${runId}`);
  state.currentRun = run;
  window.localStorage.setItem(STORAGE_KEYS.runId, run.run_id);
  updateRunUrl(run.run_id);

  await Promise.all([
    loadRunSlices(run.run_id),
    loadLensSummary(run.run_id, run.lens),
  ]);

  if (announce) {
    setMessage(
      `${titleCase(run.lens)} run loaded with ${formatCount(totalPrimaryEntities(run.result_counts))} primary entities.`,
    );
  }
  renderAll();
}

async function loadRunSlices(runId) {
  const params = new URLSearchParams();
  if (state.entityFilter !== "all") {
    params.set("entity_type", state.entityFilter);
  }

  const entityParams = new URLSearchParams(params);
  entityParams.set("limit", "24");
  if (state.focusLocationId) {
    entityParams.set("location_id", state.focusLocationId);
  }

  const clusterPath = `/api/runs/${runId}/clusters?${params.toString()}`;
  const entityPath = `/api/runs/${runId}/entities?${entityParams.toString()}`;
  const [clusters, entities] = await Promise.all([
    requestJson(clusterPath),
    requestJson(entityPath),
  ]);
  state.clusters = clusters;
  state.entities = entities;
  renderMap();
  renderEntities();
}

async function loadLensSummary(runId, lens) {
  const summaryPath = {
    sales: `/api/runs/${runId}/sales-summary`,
    recruiting: `/api/runs/${runId}/recruiting-summary`,
    investor: `/api/runs/${runId}/investor-summary`,
  }[lens];
  state.summary = summaryPath ? await requestJson(summaryPath) : null;
  renderSummary();
}

async function loadWatchlists({ quiet = false } = {}) {
  try {
    state.watchlists = await requestJson("/api/watchlists", { quiet });
    const selectedExists = state.watchlists.some(
      (watchlist) => watchlist.watchlist_id === state.selectedWatchlistId,
    );
    if (!selectedExists) {
      state.selectedWatchlistId = state.watchlists[0]?.watchlist_id || null;
    }
    if (state.selectedWatchlistId) {
      window.localStorage.setItem(STORAGE_KEYS.watchlistId, state.selectedWatchlistId);
      await loadWatchlistSignals(state.selectedWatchlistId, { quiet: true });
    } else {
      window.localStorage.removeItem(STORAGE_KEYS.watchlistId);
      state.watchlistSignals = [];
    }
    renderWatchlists();
    renderSignals();
  } catch (error) {
    console.error(error);
  }
}

async function loadWatchlistSignals(watchlistId, { quiet = false } = {}) {
  state.watchlistSignals = [];
  if (!watchlistId) {
    renderSignals();
    return;
  }
  const response = await requestJson(`/api/watchlists/${watchlistId}/signals`, { quiet });
  state.watchlistSignals = response.signals || [];
  renderSignals();
}

async function loadAuthContext() {
  try {
    state.auth = await requestJson("/api/auth/me", { quiet: true });
  } catch (error) {
    console.error(error);
  }
  renderHeader();
}

async function loadServiceHealth() {
  try {
    const response = await requestJson("/health/live", { quiet: true });
    state.liveStatus = response.status === "ok" ? "Live" : "Unavailable";
  } catch (error) {
    console.error(error);
    state.liveStatus = "Offline";
  }
  renderHeader();
}

async function loadAdminMetrics() {
  try {
    state.adminMetrics = await requestJson("/api/admin/metrics", { quiet: true });
  } catch (error) {
    state.adminMetrics = null;
  }
  renderEvents();
}

function buildRunPayload() {
  const form = refs.runForm.elements;
  const common = {
    lens: state.lens,
    title: blankToNull(form.title.value),
  };

  const searchLimit = parseInteger(form.searchLimit.value, 25);
  if (state.lens === "sales") {
    return {
      ...common,
      input: {
        search: {
          fields: DEFAULT_FIELDS.sales,
          limit: searchLimit,
        },
        preferred_industries: splitComma(form.salesPreferredIndustries.value),
        top_company_limit: parseInteger(form.salesTopCompanyLimit.value, 5),
        buyers_per_company: parseInteger(form.salesBuyersPerCompany.value, 3),
        buyer_titles: splitComma(form.salesBuyerTitles.value),
        buyer_seniorities: splitComma(form.salesBuyerSeniorities.value),
      },
    };
  }

  if (state.lens === "recruiting") {
    const radiusLat = parseFloatOrNull(form.recruitingLat.value);
    const radiusLng = parseFloatOrNull(form.recruitingLng.value);
    const radiusKm = parseFloatOrNull(form.recruitingRadiusKm.value);
    const radius =
      radiusLat !== null && radiusLng !== null && radiusKm !== null
        ? {
            latitude: radiusLat,
            longitude: radiusLng,
            radius_km: radiusKm,
          }
        : null;
    return {
      ...common,
      input: {
        search: {
          fields: DEFAULT_FIELDS.recruiting,
          limit: searchLimit,
        },
        target_titles: splitComma(form.recruitingTitles.value),
        target_seniorities: splitComma(form.recruitingSeniorities.value),
        target_functions: splitComma(form.recruitingFunctions.value),
        target_skills: splitComma(form.recruitingSkills.value),
        top_candidate_limit: parseInteger(form.recruitingTopLimit.value, 12),
        radius,
      },
    };
  }

  return {
    ...common,
    input: {
      search: {
        fields: DEFAULT_FIELDS.investor,
        limit: searchLimit,
      },
      target_markets: splitComma(form.investorMarkets.value),
      target_categories: splitComma(form.investorCategories.value),
      target_industries: splitComma(form.investorIndustries.value),
      min_headcount: parseIntegerOrNull(form.investorMinHeadcount.value),
      max_headcount: parseIntegerOrNull(form.investorMaxHeadcount.value),
      min_openings_growth_percent: parseFloatOrNull(form.investorMinOpeningsGrowth.value),
      min_follower_growth_percent: parseFloatOrNull(form.investorMinFollowerGrowth.value),
      top_company_limit: parseInteger(form.investorTopCompanyLimit.value, 5),
      founders_per_company: parseInteger(form.investorFoundersPerCompany.value, 2),
    },
  };
}

function renderAll() {
  renderHeader();
  renderHero();
  renderSummary();
  renderEntities();
  renderWatchlists();
  renderSignals();
  renderMap();
}

function renderHeader() {
  refs.userBadge.textContent = state.auth
    ? `${state.auth.user_id}${state.auth.is_admin ? " / admin" : ""}`
    : "Unavailable";
  refs.liveStatus.textContent = state.liveStatus;
  refs.runBadge.textContent = state.currentRun ? titleCase(state.currentRun.lens) : "Idle";
}

function renderHero() {
  if (!state.currentRun) {
    refs.heroTitle.textContent = "No run selected";
    refs.runMeta.textContent = "Waiting for input";
    refs.statGrid.innerHTML = buildEmptyBlock(
      "No run data yet. Launch one of the lenses to hydrate metrics, map clusters, and ranked cards.",
    );
    renderEvents();
    return;
  }

  refs.heroTitle.textContent = state.currentRun.title || `${titleCase(state.currentRun.lens)} run`;
  refs.runMeta.textContent = `${state.currentRun.status} / ${formatDateTime(state.currentRun.created_at)}`;

  const statCards = summarizeRunStats();
  refs.statGrid.innerHTML = statCards
    .map(
      (card) => `
        <div class="stat-card">
          <span class="status-inline">${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
        </div>
      `,
    )
    .join("");
  renderEvents();
}

function renderEvents() {
  const extras = state.adminMetrics
    ? `
      <div class="detail-grid">
        <span class="pill soft">users ${formatCount(state.adminMetrics.users)}</span>
        <span class="pill soft">runs ${formatCount(state.adminMetrics.search_runs)}</span>
        <span class="pill soft">watchlists ${formatCount(state.adminMetrics.watchlists)}</span>
      </div>
    `
    : "";
  refs.eventStrip.innerHTML = `
    <div class="event-message">${escapeHtml(state.message)}</div>
    ${extras}
  `;
}

function renderSummary() {
  if (!state.summary || !state.currentRun) {
    refs.summaryBody.innerHTML = buildEmptyBlock(
      "Lens summaries show up here once a run finishes. Companies or people stay actionable from the ranked cards.",
    );
    return;
  }

  let content = "";
  if (state.currentRun.lens === "sales") {
    content = renderSalesSummary();
  } else if (state.currentRun.lens === "recruiting") {
    content = renderRecruitingSummary();
  } else {
    content = renderInvestorSummary();
  }
  refs.summaryBody.innerHTML = content || buildEmptyBlock("No ranked cards returned yet.");
}

function renderSalesSummary() {
  const companies = state.summary.companies || [];
  return companies
    .map((company) => {
      const buyers = (company.buyers || [])
        .map(
          (buyer) => `
            <span class="pill soft">${escapeHtml(buyer.name)}${buyer.title ? ` / ${escapeHtml(buyer.title)}` : ""}</span>
          `,
        )
        .join("");
      return `
        <article class="summary-card">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(company.name)}</h3>
              <p class="card-subtitle">${escapeHtml(joinParts([company.domain, company.industry]))}</p>
            </div>
            <span class="pill score">${formatScore(company.lens_score)}</span>
          </div>
          <div class="detail-grid">
            <span class="pill warn">${formatCount(company.buyer_count)} buyers</span>
            <span class="pill soft">${escapeHtml(company.funding_last_round_type || "No round")}</span>
            <span class="pill soft">${escapeHtml(company.location.raw_label || "Location pending")}</span>
          </div>
          <div class="tone-bar"><div class="tone-fill" style="width: ${clampScore(company.lens_score)}%"></div></div>
          <div class="card-meta">${buyers || '<span class="empty-state">No buyers attached for this company.</span>'}</div>
          <div class="entity-actions">
            <button
              type="button"
              class="secondary-button"
              data-action="watchlist-add"
              data-entity-type="company"
              data-entity-id="${company.company_id}"
            >Track company</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderRecruitingSummary() {
  const candidates = state.summary.candidates || [];
  return candidates
    .map(
      (candidate) => `
        <article class="summary-card">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(candidate.name)}</h3>
              <p class="card-subtitle">${escapeHtml(joinParts([candidate.title, candidate.current_company_name]))}</p>
            </div>
            <span class="pill score">${formatScore(candidate.lens_score)}</span>
          </div>
          <div class="detail-grid">
            <span class="pill warn">${escapeHtml(candidate.seniority || "Unknown seniority")}</span>
            <span class="pill soft">${escapeHtml(candidate.function_category || "Function pending")}</span>
            <span class="pill soft">${escapeHtml(candidate.location.raw_label || "Location pending")}</span>
          </div>
          <div class="tone-bar"><div class="tone-fill" style="width: ${clampScore(candidate.lens_score)}%"></div></div>
          <p class="card-subtitle">${escapeHtml(candidate.headline || "No headline available.")}</p>
          <div class="entity-actions">
            <button
              type="button"
              class="secondary-button"
              data-action="watchlist-add"
              data-entity-type="person"
              data-entity-id="${candidate.person_id}"
            >Track candidate</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderInvestorSummary() {
  const companies = state.summary.companies || [];
  return companies
    .map((company) => {
      const founders = (company.founders || [])
        .map(
          (founder) => `
            <span class="pill soft">${escapeHtml(founder.name)}${founder.title ? ` / ${escapeHtml(founder.title)}` : ""}</span>
          `,
        )
        .join("");
      const signals = (company.signals || [])
        .map(
          (signal) => `
            <span class="pill signal">${escapeHtml(signal.signal_type)}</span>
          `,
        )
        .join("");
      return `
        <article class="summary-card">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(company.name)}</h3>
              <p class="card-subtitle">${escapeHtml(joinParts([company.domain, company.industry]))}</p>
            </div>
            <span class="pill score">${formatScore(company.lens_score)}</span>
          </div>
          <div class="detail-grid">
            <span class="pill warn">${formatCount(company.founder_count)} founders</span>
            <span class="pill soft">${escapeHtml(company.location.raw_label || "Location pending")}</span>
          </div>
          <div class="tone-bar"><div class="tone-fill" style="width: ${clampScore(company.lens_score)}%"></div></div>
          <div class="card-meta">${founders || '<span class="empty-state">No founders enriched.</span>'}</div>
          <div class="card-meta">${signals || '<span class="empty-state">No investor signals recorded.</span>'}</div>
          <div class="entity-actions">
            <button
              type="button"
              class="secondary-button"
              data-action="watchlist-add"
              data-entity-type="company"
              data-entity-id="${company.company_id}"
            >Track company</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderEntities() {
  const items = state.entities?.items || [];
  refs.entityCountLabel.textContent = `${formatCount(items.length)} items`;
  if (!items.length) {
    refs.entityList.innerHTML = buildEmptyBlock(
      state.currentRun
        ? "No entities match the current filter or cluster focus."
        : "Map entities land here after a run completes.",
    );
    return;
  }

  refs.entityList.innerHTML = items
    .map(
      (item) => `
        <article class="entity-card">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(item.name)}</h3>
              <p class="card-subtitle">${escapeHtml(item.subtitle || item.entity_type)}</p>
            </div>
            <span class="pill score">${formatScore(item.lens_score)}</span>
          </div>
          <div class="detail-grid">
            <span class="pill soft">${escapeHtml(item.location.raw_label || "Location pending")}</span>
            <span class="pill soft">${escapeHtml(item.location.status || "missing")}</span>
          </div>
          <div class="entity-actions">
            <button
              type="button"
              class="text-button"
              data-action="watchlist-add"
              data-entity-type="${item.entity_type}"
              data-entity-id="${item.entity_id}"
            >Add to watchlist</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderWatchlists() {
  const watchlists = state.watchlists || [];
  const selected = watchlists.find((item) => item.watchlist_id === state.selectedWatchlistId) || null;
  refs.watchlistBadge.textContent = selected
    ? `${selected.name} / ${formatCount(selected.item_count)} items`
    : "No watchlist selected";

  if (!watchlists.length) {
    refs.watchlistList.innerHTML = buildEmptyBlock(
      "Create a watchlist to track companies or people from the ranked cards.",
    );
    return;
  }

  refs.watchlistList.innerHTML = watchlists
    .map((watchlist) => {
      const isSelected = watchlist.watchlist_id === state.selectedWatchlistId;
      const items = (watchlist.items || [])
        .slice(0, 4)
        .map(
          (item) => `
            <div class="watchlist-meta">
              <span class="pill soft">${escapeHtml(item.entity.name)}</span>
              <button
                type="button"
                class="text-button destructive"
                data-action="remove-watchlist-item"
                data-watchlist-id="${watchlist.watchlist_id}"
                data-item-id="${item.item_id}"
              >Remove</button>
            </div>
          `,
        )
        .join("");

      return `
        <article class="watchlist-card${isSelected ? " selected-card" : ""}">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(watchlist.name)}</h3>
              <p class="card-subtitle">${escapeHtml(watchlist.description || "No description")}</p>
            </div>
            <span class="pill warn">${formatCount(watchlist.item_count)} items</span>
          </div>
          <div class="watchlist-actions">
            <button
              type="button"
              class="text-button"
              data-action="select-watchlist"
              data-watchlist-id="${watchlist.watchlist_id}"
            >${isSelected ? "Selected" : "Open"}</button>
            <span class="pill soft">${escapeHtml(watchlist.lens || "mixed")}</span>
          </div>
          ${items || '<div class="empty-state">No tracked entities yet.</div>'}
        </article>
      `;
    })
    .join("");
}

function renderSignals() {
  if (!state.selectedWatchlistId) {
    refs.signalTimeline.innerHTML = buildEmptyBlock(
      "Select a watchlist to inspect the latest entity signals and refresh output.",
    );
    return;
  }
  if (!state.watchlistSignals.length) {
    refs.signalTimeline.innerHTML = buildEmptyBlock(
      "No signals recorded yet for this watchlist. Run refresh after enriching tracked entities.",
    );
    return;
  }

  refs.signalTimeline.innerHTML = state.watchlistSignals
    .slice(0, 12)
    .map(
      (signal) => `
        <article class="timeline-card">
          <div class="card-title-row">
            <div class="card-title">
              <h3>${escapeHtml(signal.title || signal.signal_type)}</h3>
              <p class="card-subtitle">${escapeHtml(joinParts([signal.entity_name, signal.entity_type]))}</p>
            </div>
            <span class="pill signal">${escapeHtml(signal.signal_type)}</span>
          </div>
          <p>${escapeHtml(signal.description || "No description provided.")}</p>
          <div class="timeline-meta">
            <span class="pill soft">${formatDateTime(signal.occurred_at || signal.created_at)}</span>
            <span class="pill soft">confidence ${Math.round((signal.confidence || 0) * 100)}%</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderMap() {
  const clusters = state.clusters?.clusters || [];
  const summary = state.clusters?.summary;
  refs.mapLegend.innerHTML = summary ? `
      <div class="legend-row">
        <span class="legend-chip"><span class="swatch" style="background:#ffb703"></span>Total ${formatCount(summary.total_entities)}</span>
        <span class="legend-chip"><span class="swatch" style="background:#0f766e"></span>Mapped ${formatCount(summary.mapped_count)}</span>
        <span class="legend-chip"><span class="swatch" style="background:#d95d39"></span>Unmapped ${formatCount(summary.unmapped_count)}</span>
      </div>
    ` : "";

  if (!clusters.length) {
    refs.mapSvg.innerHTML = buildMapSkeleton(
      "<text x='490' y='270' class='map-empty'>No geo clusters available for the current selection.</text>",
    );
    refs.clusterDetail.innerHTML = "<p class='cluster-placeholder'>Select a run to render mapped clusters.</p>";
    return;
  }

  const bounds = deriveBounds(clusters);
  const nodes = clusters
    .map((cluster) => renderClusterNode(cluster, bounds))
    .join("");
  refs.mapSvg.innerHTML = buildMapSkeleton(nodes);

  const selected = clusters.find((cluster) => cluster.cluster_id === state.selectedClusterId);
  refs.clusterDetail.innerHTML = selected
    ? `
        <div class="detail-grid">
          <span class="pill soft">${formatCount(selected.entity_count)} entities</span>
          <span class="pill soft">${formatCount(selected.location_count)} locations</span>
        </div>
        <p class="cluster-placeholder">${escapeHtml(selected.labels.join(" / ") || "Cluster focus")}</p>
      `
    : "<p class='cluster-placeholder'>Click a node to focus a location slice when a single location is present.</p>";
}

function renderClusterNode(cluster, bounds) {
  const { x, y } = projectPoint(cluster.latitude, cluster.longitude, bounds);
  const radius = cluster.is_cluster
    ? Math.min(28, 10 + Math.log2(cluster.entity_count + 1) * 5)
    : 9;
  const fill = cluster.company_count && cluster.person_count
    ? "#ffb703"
    : cluster.company_count
      ? "#0f766e"
      : "#d95d39";
  const opacity = cluster.cluster_id === state.selectedClusterId ? 1 : 0.88;
  const label = cluster.is_cluster ? String(cluster.entity_count) : "";

  return `
    <g class="map-node" data-cluster-id="${cluster.cluster_id}" transform="translate(${x}, ${y})">
      <circle class="map-node-glow" r="${radius + 8}" fill="${fill}" opacity="0.18"></circle>
      <circle class="map-node-core" r="${radius}" fill="${fill}" opacity="${opacity}"></circle>
      <circle class="map-node-ring" r="${radius + 2.5}" fill="none" stroke="rgba(255,248,237,0.75)" stroke-width="1.5"></circle>
      ${label ? `<text class="map-node-text" text-anchor="middle" dy="5">${label}</text>` : ""}
    </g>
  `;
}

function buildMapSkeleton(nodes) {
  const gridLines = [];
  for (let x = 120; x <= 860; x += 148) {
    gridLines.push(`<line class="map-grid-line" x1="${x}" y1="40" x2="${x}" y2="500"></line>`);
  }
  for (let y = 80; y <= 460; y += 76) {
    gridLines.push(`<line class="map-grid-line" x1="40" y1="${y}" x2="940" y2="${y}"></line>`);
  }
  return `
    <rect x="24" y="24" width="932" height="492" rx="28" class="map-surface"></rect>
    <g class="map-grid">${gridLines.join("")}</g>
    <path class="map-wave" d="M100 388C178 352 244 300 346 288C434 278 530 312 626 286C712 262 782 206 900 174"></path>
    <path class="map-wave faint" d="M84 188C166 222 262 238 352 208C426 184 474 126 572 124C664 122 756 188 904 224"></path>
    ${nodes}
  `;
}

function deriveBounds(clusters) {
  const lats = clusters.map((item) => item.latitude);
  const lngs = clusters.map((item) => item.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const latPad = Math.max(4, (maxLat - minLat) * 0.18);
  const lngPad = Math.max(6, (maxLng - minLng) * 0.18);
  return {
    minLat: clamp(minLat - latPad, -85, 85),
    maxLat: clamp(maxLat + latPad, -85, 85),
    minLng: clamp(minLng - lngPad, -180, 180),
    maxLng: clamp(maxLng + lngPad, -180, 180),
  };
}

function projectPoint(latitude, longitude, bounds) {
  const width = 980;
  const height = 540;
  const padX = 56;
  const padY = 48;
  const usableWidth = width - padX * 2;
  const usableHeight = height - padY * 2;
  const x = padX + ((longitude - bounds.minLng) / (bounds.maxLng - bounds.minLng || 1)) * usableWidth;
  const y = padY + (1 - (latitude - bounds.minLat) / (bounds.maxLat - bounds.minLat || 1)) * usableHeight;
  return {
    x: clamp(x, padX, width - padX),
    y: clamp(y, padY, height - padY),
  };
}

function summarizeRunStats() {
  if (!state.currentRun) {
    return [];
  }
  const counts = state.currentRun.result_counts || {};
  const base = [
    { label: "Status", value: titleCase(state.currentRun.status) },
    {
      label: "Primary entities",
      value: formatCount(totalPrimaryEntities(counts)),
    },
    {
      label: "Locations",
      value: formatCount(counts.locations || state.clusters?.summary?.mapped_count || 0),
    },
  ];

  if (state.currentRun.lens === "sales" && state.summary?.summary) {
    return base.concat([
      { label: "Buyers", value: formatCount(state.summary.summary.buyer_count) },
      { label: "Average score", value: formatScore(state.summary.summary.average_company_score) },
    ]);
  }
  if (state.currentRun.lens === "recruiting" && state.summary?.summary) {
    return base.concat([
      { label: "Employers", value: formatCount(state.summary.summary.employer_count) },
      { label: "Average score", value: formatScore(state.summary.summary.average_candidate_score) },
    ]);
  }
  if (state.currentRun.lens === "investor" && state.summary?.summary) {
    return base.concat([
      { label: "Founders", value: formatCount(state.summary.summary.founder_count) },
      { label: "Signals", value: formatCount(state.summary.summary.signal_count) },
    ]);
  }
  return base;
}

function totalPrimaryEntities(resultCounts) {
  return resultCounts.companies || resultCounts.people || 0;
}

async function requestJson(path, { method = "GET", body, quiet = false } = {}) {
  const options = {
    method,
    headers: {
      Accept: "application/json",
    },
  };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = payload?.error?.message || `Request failed with status ${response.status}.`;
    if (!quiet) {
      setMessage(message);
    }
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

function setBusy(isBusy) {
  state.isBusy = isBusy;
  refs.runButton.disabled = isBusy;
  refs.reloadRunButton.disabled = isBusy;
  refs.refreshWatchlistButton.disabled = isBusy;
}

function setMessage(message) {
  state.message = message;
  renderEvents();
}

function updateRunUrl(runId) {
  const url = new URL(window.location.href);
  if (runId) {
    url.searchParams.set("run", runId);
  } else {
    url.searchParams.delete("run");
  }
  window.history.replaceState({}, "", url);
}

function buildEmptyBlock(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function splitComma(value) {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function parseInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseIntegerOrNull(value) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseFloatOrNull(value) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function blankToNull(value) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatCount(value) {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(Number(value || 0));
}

function formatScore(value) {
  if (value === null || value === undefined) {
    return "0";
  }
  return Number(value).toFixed(1);
}

function clampScore(value) {
  return clamp(Number(value || 0), 0, 100);
}

function formatDateTime(value) {
  if (!value) {
    return "Pending";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Pending";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function titleCase(value) {
  return String(value || "")
    .split("_")
    .join(" ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function joinParts(parts) {
  return parts.filter(Boolean).join(" / ");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
