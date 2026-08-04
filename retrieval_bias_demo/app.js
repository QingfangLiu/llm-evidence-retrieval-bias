(function () {
  const data = window.RETRIEVAL_BIAS_DEMO_DATA || {};
  const app = document.getElementById("app");
  const reviewId = document.getElementById("review-id");
  const reviewTitle = document.getElementById("review-title");
  const experimentNav = document.getElementById("experiment-nav");

  if (!app || !reviewId || !reviewTitle || !experimentNav) {
    return;
  }

  const experiments = Array.isArray(data.experiments) ? data.experiments : [];
  const crossReviewSummary = data.crossReviewSummary?.viewType === "cross-review"
    ? data.crossReviewSummary
    : null;
  const navigationItems = crossReviewSummary
    ? [crossReviewSummary, ...experiments]
    : experiments;
  let activeExperiment = {};
  let conditions = [];
  let modelSummaries = [];
  let sections = {};
  let overview = {};
  let venn = {};
  let activeSection = "included";

  const vennRegionPositions = {
    2: {
      firstOnly: [85, 124],
      secondOnly: [235, 124],
      both: [160, 124],
    },
    3: {
      firstOnly: [85, 91],
      secondOnly: [235, 91],
      thirdOnly: [160, 211],
      firstSecondOnly: [160, 66],
      firstThirdOnly: [112, 153],
      secondThirdOnly: [208, 153],
      allThree: [160, 118],
    },
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function text(value, fallback = "") {
    const clean = String(value ?? "").trim();
    return clean ? escapeHtml(clean) : fallback;
  }

  function number(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toLocaleString() : "0";
  }

  function percent(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${Math.round(numeric * 100)}%` : "0%";
  }

  function precisePercent(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(1)}%` : "—";
  }

  function percentagePoints(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric)
      ? `${(numeric * 100).toFixed(1)} percentage points`
      : "—";
  }

  function permutationPValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "—";
    }
    return numeric < 0.001 ? "<0.001" : numeric.toFixed(3);
  }

  function average(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    const numeric = Number(value);
    return Number.isFinite(numeric)
      ? numeric.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
      : "0.00";
  }

  function modelGroups() {
    const groups = [];
    conditions.forEach((condition, conditionIndex) => {
      let group = groups.find((item) => item.model === condition.model);
      if (!group) {
        const summary = modelSummaries.find((item) => item.model === condition.model) || {};
        group = {
          model: condition.model,
          modelLabel: condition.modelLabel,
          modelSetting: condition.modelSetting,
          responseCount: summary.responseCount,
          averageCitationCount: summary.averageCitationCount,
          conditions: [],
        };
        groups.push(group);
      }
      group.conditions.push({ ...condition, conditionIndex });
    });
    return groups;
  }

  function isGroupEnd(conditionIndex) {
    return !conditions[conditionIndex + 1]
      || conditions[conditionIndex + 1].model !== conditions[conditionIndex].model;
  }

  function rateClass(rate) {
    if (rate <= 0) return "rate-zero";
    if (rate <= 0.25) return "rate-low";
    if (rate <= 0.5) return "rate-mid";
    if (rate < 1) return "rate-high";
    return "rate-full";
  }

  function renderReviewHeader() {
    const review = activeExperiment.review || {};
    reviewId.textContent = review.reviewId || "";
    reviewTitle.textContent = review.reviewTitle || "";
  }

  function renderExperimentNavigation() {
    experimentNav.innerHTML = navigationItems.map((experiment) => {
      const experimentId = experiment.viewId || experiment.experimentId;
      const activeExperimentId = activeExperiment.viewId || activeExperiment.experimentId;
      return `
      <a
        class="experiment-link ${experimentId === activeExperimentId ? "active" : ""}"
        href="#${text(experimentId)}"
        aria-current="${experimentId === activeExperimentId ? "page" : "false"}"
      >${text(experiment.navigationLabel)}</a>
    `;
    }).join("");
  }

  function selectExperimentFromHash() {
    const requestedId = window.location.hash.replace(/^#/, "");
    activeExperiment = navigationItems.find(
      (experiment) => (experiment.viewId || experiment.experimentId) === requestedId,
    ) || navigationItems[0] || {};
    conditions = Array.isArray(activeExperiment.conditions) ? activeExperiment.conditions : [];
    modelSummaries = Array.isArray(activeExperiment.modelSummaries)
      ? activeExperiment.modelSummaries
      : [];
    sections = activeExperiment.sections || {};
    overview = activeExperiment.overview || {};
    venn = activeExperiment.venn || {};
    renderReviewHeader();
    renderExperimentNavigation();
    render();
  }

  function vennRegionLabel(panel, region) {
    const memberLabels = (region.memberIndexes || []).map(
      (memberIndex) => panel.setLabels?.[memberIndex] || `Set ${memberIndex + 1}`,
    );
    if (memberLabels.length === panel.setLabels?.length) {
      return memberLabels.length === 2 ? "Both sets" : "All three sets";
    }
    return `${memberLabels.join(" + ")} only`;
  }

  function renderVennPanel(panel) {
    const setLabels = Array.isArray(panel.setLabels) ? panel.setLabels : [];
    const setCounts = Array.isArray(panel.setCounts) ? panel.setCounts : [];
    const regions = Array.isArray(panel.regions) ? panel.regions : [];
    const setCount = setLabels.length;
    const regionPositions = vennRegionPositions[setCount] || {};
    const overlapOrderLabel = setCount === 2 ? "2-way" : "3-way";
    const sharedSetLabel = setCount === 2 ? "both sets" : "all three sets";
    const benchmarkStudyCount = Number(panel.benchmarkStudyCount) || 0;
    const universeLabel = text(panel.universeLabel, "Cochrane included studies");
    const unionCount = Number(panel.unionCount) || 0;
    const sharedAllCount = Number(panel.sharedAllCount) || 0;
    const permutationBaseline = panel.permutationBaseline || {};
    const permutationInterval = permutationBaseline.interval95 || {};
    const lowerTailPValue = Number(permutationBaseline.lowerTailPValue);
    const hasLowerTailTest = Number.isFinite(lowerTailPValue);
    const significantlyBelow = permutationBaseline.significantlyBelowAt05 === true;
    const recallTest = panel.recallPermutationTest || null;
    const notRecalledCount = Math.max(benchmarkStudyCount - unionCount, 0);
    const hasOutsideCount = benchmarkStudyCount > unionCount;
    const rateLabel = hasOutsideCount ? "Recall" : "Share";
    const legend = setLabels.map((setLabel, setIndex) => {
      const recalledCount = Number(setCounts[setIndex]) || 0;
      const recall = benchmarkStudyCount ? recalledCount / benchmarkStudyCount : null;
      return `
        <span class="venn-set-label">
          <i class="venn-swatch venn-set-${setIndex + 1}" aria-hidden="true"></i>
          <strong>${text(setLabel)}</strong>
          <small>${rateLabel} ${number(recalledCount)}/${number(benchmarkStudyCount)} (${precisePercent(recall)})</small>
        </span>
      `;
    }).join("");
    const regionMarks = regions.map((region) => {
      const [x, y] = regionPositions[region.regionId] || [160, 120];
      const regionLabel = vennRegionLabel(panel, region);
      const studyLabels = Array.isArray(region.studyLabels) ? region.studyLabels : [];
      const tooltip = `${regionLabel}: ${number(region.studyCount)}. ${studyLabels.length ? studyLabels.join("; ") : "No studies."}`;
      return `
        <g class="venn-region ${region.studyCount ? "" : "venn-region-zero"}" aria-label="${text(tooltip)}">
          <title>${text(tooltip)}</title>
          <circle class="venn-region-target" cx="${x}" cy="${y}" r="17"></circle>
          <text x="${x}" y="${y}">${number(region.studyCount)}</text>
        </g>
      `;
    }).join("");
    const circleMarks = setCount === 2
      ? `
        <circle class="venn-circle venn-circle-first" cx="118" cy="124" r="82"></circle>
        <circle class="venn-circle venn-circle-second" cx="202" cy="124" r="82"></circle>
      `
      : `
        <circle class="venn-circle venn-circle-first" cx="121" cy="95" r="78"></circle>
        <circle class="venn-circle venn-circle-second" cx="199" cy="95" r="78"></circle>
        <circle class="venn-circle venn-circle-third" cx="160" cy="166" r="78"></circle>
      `;
    const lowerTailSummary = hasLowerTailTest
      ? ` Lower-tail permutation p ${permutationPValue(lowerTailPValue)}; significantly below the null at 0.05: ${significantlyBelow ? "yes" : "no"}.`
      : "";
    const recallSummary = recallTest
      ? ` Recall difference across sets: mean-recall range ${percentagePoints(recallTest.observedStatistic)}, blocked permutation p${permutationPValue(recallTest.pValue)}, significant at 0.05: ${recallTest.significantAt05 ? "yes" : "no"}.`
      : "";
    const outsideSummary = hasOutsideCount
      ? ` Not recalled by any condition ${number(notRecalledCount)}.`
      : "";
    const diagramSummary = `${panel.title}. ${setCount}-set Venn diagram within ${number(benchmarkStudyCount)} ${universeLabel}. Observed ${overlapOrderLabel} Jaccard ${precisePercent(panel.multiSetJaccard)}, based on ${number(sharedAllCount)} studies shared by ${sharedSetLabel} out of ${number(unionCount)} in their union. Permutation-null mean ${precisePercent(permutationBaseline.meanJaccard)}, with a 95 percent null interval from ${precisePercent(permutationInterval.lower)} to ${precisePercent(permutationInterval.upper)}.${lowerTailSummary}${recallSummary}${outsideSummary} Circle areas are schematic.`;
    return `
      <article class="venn-panel venn-panel-${text(panel.colorScheme)}">
        <header class="venn-panel-heading">
          <div>
            <h4>${text(panel.title)}</h4>
            <p>${text(panel.subtitle)}</p>
          </div>
        </header>
        <div class="venn-plot-layout">
          <figure class="venn-universe-figure">
            <div class="venn-universe ${hasOutsideCount ? "" : "venn-universe-no-outside"}">
              <svg
                class="venn-diagram"
                viewBox="0 0 320 248"
                role="img"
                aria-label="${text(diagramSummary)}"
              >
                ${circleMarks}
                ${regionMarks}
              </svg>
              ${hasOutsideCount ? `
                <p class="venn-unrecalled">
                  Outside all circles <strong>Not recalled: ${number(notRecalledCount)}</strong>
                </p>
              ` : ""}
            </div>
            <figcaption class="venn-universe-caption">
              ${universeLabel} <strong>N=${number(benchmarkStudyCount)}</strong>
            </figcaption>
          </figure>
          <div class="venn-legend-summary">
            <div class="venn-set-labels" aria-label="Venn sets">${legend}</div>
            <div class="venn-panel-metrics">
              <span>Observed ${overlapOrderLabel} Jaccard <strong>${precisePercent(panel.multiSetJaccard)}</strong> (${number(sharedAllCount)}/${number(unionCount)})</span>
              <span>Permutation-null mean <strong>${precisePercent(permutationBaseline.meanJaccard)}</strong></span>
              <small>95% null interval ${precisePercent(permutationInterval.lower)}–${precisePercent(permutationInterval.upper)}</small>
              ${hasLowerTailTest ? `
                <small>Significantly below null: <strong>${significantlyBelow ? "Yes" : "No"}</strong> · lower-tail p${permutationPValue(lowerTailPValue)}</small>
              ` : ""}
            </div>
            ${recallTest ? `
              <div class="venn-panel-metrics venn-recall-metrics">
                <span>Recall difference at p&lt;0.05 <strong>${recallTest.significantAt05 ? "Yes" : "No"}</strong></span>
                <small>Mean-recall range ${percentagePoints(recallTest.observedStatistic)} · blocked permutation p${permutationPValue(recallTest.pValue)}</small>
              </div>
            ` : ""}
          </div>
        </div>
      </article>
    `;
  }

  function renderVennSmallMultiples() {
    const panelGroups = Array.isArray(venn.panelGroups) ? venn.panelGroups : [];
    if (!panelGroups.some((group) => Array.isArray(group.panels) && group.panels.length)) {
      return "";
    }
    const groupMarkup = panelGroups.map((group) => {
      const panels = Array.isArray(group.panels) ? group.panels : [];
      if (!panels.length) {
        return "";
      }
      const headingId = `venn-group-${group.groupId}`;
      const heading = group.title
        ? `
          <header class="venn-analysis-heading">
            <h3 id="${text(headingId)}">${text(group.title)}</h3>
            <p>${text(group.description)}</p>
          </header>
        `
        : "";
      return `
        <section
          class="venn-analysis-group"
          ${group.title ? `aria-labelledby="${text(headingId)}"` : ""}
        >
          ${heading}
          <div class="venn-grid">${panels.map(renderVennPanel).join("")}</div>
        </section>
      `;
    }).join("");
    return `
      <section class="panel venn-section" aria-labelledby="venn-title">
        <div class="venn-heading">
          <div>
            <h2 id="venn-title">Overlap of recalled Cochrane trials</h2>
          </div>
          <p>${text(venn.membershipRule)}. Region counts are exact; circle areas are schematic. Hover a count for study names.</p>
        </div>
        ${groupMarkup}
      </section>
    `;
  }

  function renderControls() {
    const toneClass = activeSection === "included" ? "included-tone" : "excluded-tone";
    return `
      <div class="matrix-controls">
        <div class="study-tabs" role="tablist" aria-label="Cochrane reference status">
          <button
            class="study-tab ${activeSection === "included" ? "active" : ""}"
            type="button"
            role="tab"
            aria-selected="${activeSection === "included"}"
            data-section="included"
          >Included <span>${number(overview.includedStudyCount)}</span></button>
          <button
            class="study-tab ${activeSection === "excluded" ? "active" : ""}"
            type="button"
            role="tab"
            aria-selected="${activeSection === "excluded"}"
            data-section="excluded"
          >Excluded <span>${number(overview.excludedStudyCount)}</span></button>
        </div>
        <div class="matrix-legend" aria-label="Matrix legend">
          <span>Average retrieval</span>
          <span><i class="legend-rate rate-zero">0%</i></span>
          <span><i class="legend-rate rate-mid ${toneClass}">50%</i></span>
          <span><i class="legend-rate rate-full ${toneClass}">100%</i></span>
          <span><i class="legend-issue"></i>Citation issue</span>
        </div>
      </div>
    `;
  }

  function statusCell(result, study, condition) {
    const retrievedCount = Number(result?.retrievedCount) || 0;
    const repetitionCount = Number(result?.repetitionCount) || condition.repetitionCount || 0;
    if (repetitionCount <= 0) {
      const emptyLabel = `${study.studyLabel} — ${condition.modelLabel}, ${condition.conditionLabel}: not run.`;
      return `
        <span
          class="retrieval-rate rate-empty"
          aria-label="${text(emptyLabel)}"
          title="${text(emptyLabel)}"
        >—</span>
      `;
    }
    const retrievalRate = Number(result?.retrievalRate) || 0;
    const identityIssueCount = Number(result?.identityIssueCount) || 0;
    const toneClass = activeSection === "included" ? "included-tone" : "excluded-tone";
    const issueText = identityIssueCount
      ? ` ${identityIssueCount} citation issue${identityIssueCount === 1 ? "" : "s"}.`
      : "";
    const title = `${study.studyLabel} — ${condition.modelLabel}, ${condition.conditionLabel}: ${retrievedCount}/${repetitionCount} repetitions (${percent(retrievalRate)}).${issueText}`;
    return `
      <span
        class="retrieval-rate ${toneClass} ${rateClass(retrievalRate)} ${identityIssueCount ? "has-identity-issue" : ""}"
        aria-label="${text(title)}"
        title="${text(title)}"
      >${percent(retrievalRate)}</span>
    `;
  }

  function renderMatrix(studies) {
    const groups = modelGroups();
    const groupHeaders = groups.map((group) => `
      <th class="model-group-head" colspan="${group.conditions.length}">
        <strong>${text(group.modelLabel)}</strong>
        <span>${text(group.modelSetting)}</span>
        <small>${number(group.responseCount)} answers · ${average(group.averageCitationCount)} avg citations/answer</small>
      </th>
    `).join("");
    const conditionHeaders = conditions.map((condition, conditionIndex) => `
      <th
        class="condition-head ${isGroupEnd(conditionIndex) ? "group-end" : ""}"
        title="${text(condition.conditionPrompt)}"
      >
        <strong>${text(condition.conditionLabel)}</strong>
        <small>${condition.repetitionCount
          ? `n=${number(condition.repetitionCount)} · ${average(condition.averageCitationCount)} avg citations`
          : "Not run"}</small>
      </th>
    `).join("");
    const rows = studies.map((study) => {
      const studyTitle = study.referenceExcerpt || study.studyLabel;
      const cells = conditions.map((condition, conditionIndex) => `
        <td class="matrix-cell ${isGroupEnd(conditionIndex) ? "group-end" : ""}">
          ${statusCell(study.conditionResults?.[conditionIndex], study, condition)}
        </td>
      `).join("");
      return `
        <tr>
          <th class="study-cell" scope="row" title="${text(studyTitle)}">
            <span>${text(study.studyLabel)}</span>
            <small>${number(study.retrievedCount)}/${number(overview.repetitionCount)} repetitions</small>
          </th>
          ${cells}
        </tr>
      `;
    }).join("");

    return `
      <div class="matrix-wrap" tabindex="0" aria-label="Average study retrieval by chatbot and condition">
        <table class="retrieval-matrix">
          <thead>
            <tr>
              <th class="study-head" rowspan="2">Cochrane study</th>
              ${groupHeaders}
            </tr>
            <tr>${conditionHeaders}</tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function renderSummaryDimension(dimension, metric, scaleMaximum) {
    const items = Array.isArray(dimension.items) ? dimension.items : [];
    const metricHeading = "Mean ± SD";
    const scaleLabel = metric === "citations"
      ? `0–${number(scaleMaximum)}`
      : "0–100%";
    const numericValue = (item) => Number(
      metric === "citations" ? item.meanCitationCount
        : metric === "recall" ? item.meanRecall
        : metric === "jaccardAll" ? item.meanJaccardAllCandidates
        : item.meanJaccardIncludedOnly
    );
    const barWidth = (item) => {
      const value = numericValue(item);
      if (!Number.isFinite(value) || !Number.isFinite(scaleMaximum) || scaleMaximum <= 0) {
        return 0;
      }
      return Math.min(100, Math.max(0, value / scaleMaximum * 100));
    };
    const valueMarkup = (item) => {
      if (metric === "citations") {
        return `${average(item.meanCitationCount)} ± ${average(item.citationCountSd)}`;
      }
      if (metric === "recall") {
        return `${precisePercent(item.meanRecall)} ± ${precisePercent(item.recallSd)}`;
      }
      if (metric === "jaccardAll") {
        return `${precisePercent(item.meanJaccardAllCandidates)} ± ${precisePercent(item.jaccardAllCandidatesSd)}`;
      }
      return `${precisePercent(item.meanJaccardIncludedOnly)} ± ${precisePercent(item.jaccardIncludedOnlySd)}`;
    };
    const recallTest = dimension.recallPermutationTest || {};
    const testMarkup = metric === "recall"
      ? `
        <div class="summary-test">
          <span>Overall difference at p&lt;0.05 <strong>${recallTest.significantAt05 ? "Yes" : "No"}</strong></span>
          <small>Mean-recall range ${percentagePoints(recallTest.observedStatistic)} · blocked permutation p${permutationPValue(recallTest.pValue)}</small>
          <small>No pairwise post-hoc tests shown.</small>
        </div>
      `
      : "";
    return `
      <article class="summary-dimension">
        <h3>${text(dimension.title)}</h3>
        <div class="summary-table-wrap">
          <table class="summary-table">
            <thead>
              <tr>
                <th scope="col">Group</th>
                <th class="summary-bar-heading" scope="col">Mean bar <span>${scaleLabel}</span></th>
                <th scope="col">${metricHeading}</th>
              </tr>
            </thead>
            <tbody>
              ${items.map((item) => `
                <tr>
                  <th scope="row">${text(item.label)}</th>
                  <td class="summary-bar-cell">
                    <span class="summary-bar-track" aria-hidden="true">
                      <span
                        class="summary-bar-fill"
                        data-group-id="${text(item.groupId)}"
                        style="width: ${barWidth(item).toFixed(2)}%"
                      ></span>
                    </span>
                  </td>
                  <td><strong>${valueMarkup(item)}</strong></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
        ${testMarkup}
      </article>
    `;
  }

  function computeDistributionDomain(items, scale) {
    const allValues = items.flatMap((item) => [
      item.stats.min, item.stats.max, ...item.stats.outliers,
    ]);
    const low = Math.min(...allValues);
    const high = Math.max(...allValues);
    if (scale === "log") {
      return { min: Math.max(1, low * 0.85), max: high * 1.15 };
    }
    const span = high - low || 1;
    return { min: low - span * 0.06, max: high + span * 0.06 };
  }

  function makeDistributionScale(domain, scale) {
    if (scale === "log") {
      const logMin = Math.log10(domain.min);
      const logMax = Math.log10(domain.max);
      // A value of 0 (e.g. zero citations/year) has no defined log position;
      // clamp it to the left edge rather than letting log10(0) = -Infinity
      // through, which would place the point off the plot entirely.
      return (value) => {
        if (value <= 0) {
          return 0;
        }
        const position = ((Math.log10(value) - logMin) / (logMax - logMin)) * 100;
        return Math.max(0, Math.min(100, position));
      };
    }
    return (value) => ((value - domain.min) / (domain.max - domain.min)) * 100;
  }

  function distributionTicks(domain, scale) {
    if (scale === "log") {
      const candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000];
      return candidates.filter((tick) => tick >= domain.min && tick <= domain.max);
    }
    const tickCount = 5;
    const rawStep = (domain.max - domain.min) / tickCount || 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
    const step = Math.max(1, Math.round(rawStep / magnitude) * magnitude);
    const start = Math.ceil(domain.min / step) * step;
    const ticks = [];
    for (let tick = start; tick <= domain.max; tick += step) {
      ticks.push(Math.round(tick));
    }
    return ticks;
  }

  // Deterministic jitter so repeated views place the same point at the same
  // offset. Uses a golden-ratio low-discrepancy sequence rather than a short
  // repeating pattern, so runs of tied values (e.g. the same publication
  // year) spread out smoothly instead of forming a repeating rosette shape.
  function jitterOffset(index) {
    const fraction = (index * 0.6180339887) % 1;
    return fraction * 2 - 1;
  }

  function renderDistributionRow(item, xScale, formatValue) {
    const s = item.stats;
    const centerY = 20;
    const boxTop = centerY - 8;
    const q1X = xScale(s.q1);
    const q3X = xScale(s.q3);
    const dots = s.values.map((value, index) => `
      <circle
        class="distribution-dot"
        data-group-id="${text(item.groupId)}"
        cx="${xScale(value).toFixed(2)}"
        cy="${(centerY + jitterOffset(index) * 13).toFixed(1)}"
        r="1.4"
      ></circle>
    `).join("");
    const outlierMarks = s.outliers.map((value) => `
      <circle
        class="distribution-outlier"
        data-group-id="${text(item.groupId)}"
        cx="${xScale(value).toFixed(2)}"
        cy="${centerY}"
        r="2.2"
      ></circle>
    `).join("");
    const iqrLabel = `${formatValue(s.median)} (${formatValue(s.q1)}–${formatValue(s.q3)})`;
    return `
      <div class="distribution-row">
        <div class="distribution-row-label">
          <strong>${text(item.label)}</strong>
          <small>n=${number(s.n)} · median ${text(iqrLabel)}</small>
        </div>
        <svg
          class="distribution-plot"
          viewBox="0 0 100 40"
          preserveAspectRatio="none"
          role="img"
          aria-label="${text(item.label)}: n=${s.n}, median ${text(iqrLabel)}"
        >
          <line
            class="distribution-whisker"
            data-group-id="${text(item.groupId)}"
            x1="${xScale(s.whiskerLow).toFixed(2)}"
            x2="${xScale(s.whiskerHigh).toFixed(2)}"
            y1="${centerY}"
            y2="${centerY}"
          ></line>
          ${dots}
          <rect
            class="distribution-box"
            data-group-id="${text(item.groupId)}"
            x="${Math.min(q1X, q3X).toFixed(2)}"
            y="${boxTop}"
            width="${Math.max(0.6, Math.abs(q3X - q1X)).toFixed(2)}"
            height="16"
          ></rect>
          <line
            class="distribution-median"
            data-group-id="${text(item.groupId)}"
            x1="${xScale(s.median).toFixed(2)}"
            x2="${xScale(s.median).toFixed(2)}"
            y1="${boxTop}"
            y2="${boxTop + 16}"
          ></line>
          ${outlierMarks}
        </svg>
      </div>
    `;
  }

  function renderDistributionTestDetail(test) {
    if (test.method === "Kruskal-Wallis H") {
      const groupSummary = test.groupLabels
        .map((label, index) => `${label} n=${number(test.sampleSizes[index])}`)
        .join(", ");
      return `${text(test.method)}, ${text(groupSummary)} · p${permutationPValue(test.pValue)}`;
    }
    return `${text(test.method)}, ${text(test.comparisonLabel)} (n=${number(test.sampleSizeA)} vs. n=${number(test.sampleSizeB)}) · p${permutationPValue(test.pValue)}`;
  }

  function renderDunnPosthocTable(posthoc) {
    if (!Array.isArray(posthoc) || !posthoc.length) {
      return "";
    }
    const rows = posthoc.map((comparison) => `
      <tr>
        <th scope="row">${text(comparison.groupLabelA)} vs. ${text(comparison.groupLabelB)}</th>
        <td>${(comparison.meanRankA - comparison.meanRankB).toFixed(1)}</td>
        <td>${comparison.zStatistic.toFixed(2)}</td>
        <td>${permutationPValue(comparison.pValueRaw)}</td>
        <td>${permutationPValue(comparison.pValueBonferroni)}${text(significanceStars(comparison.pValueBonferroni))}</td>
      </tr>
    `).join("");
    return `
      <div class="summary-table-wrap posthoc-wrap">
        <table class="summary-table logistic-regression-table posthoc-table">
          <thead>
            <tr>
              <th scope="col">Pairwise comparison (Dunn's test)</th>
              <th scope="col">Mean rank diff.</th>
              <th scope="col">z</th>
              <th scope="col">Raw p</th>
              <th scope="col">Bonferroni p</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function renderDistributionCard(title, scale, domain, formatValue, items, test, posthoc) {
    const xScale = makeDistributionScale(domain, scale);
    const rows = items.map((item) => renderDistributionRow(item, xScale, formatValue)).join("");
    const axisMarks = distributionTicks(domain, scale).map((tick) => `
      <span class="distribution-tick" style="left: ${xScale(tick).toFixed(2)}%">${text(formatValue(tick))}</span>
    `).join("");
    const testMarkup = test ? `
      <div class="summary-test">
        <span>Difference at p&lt;0.05 <strong>${test.significantAt05 ? "Yes" : "No"}</strong></span>
        <small>${renderDistributionTestDetail(test)}</small>
      </div>
    ` : "";
    const posthocMarkup = posthoc ? renderDunnPosthocTable(posthoc) : "";
    return `
      <article class="summary-dimension distribution-card">
        <h3>${text(title)}</h3>
        <div class="distribution-rows">
          ${rows}
          <div class="distribution-row distribution-axis-row">
            <div class="distribution-row-label" aria-hidden="true"></div>
            <div class="distribution-axis-track">${axisMarks}</div>
          </div>
        </div>
        ${testMarkup}
        ${posthocMarkup}
      </article>
    `;
  }

  function renderCharacteristicDistributions() {
    const distributions = activeExperiment.characteristicDistributions;
    if (!distributions) {
      return "";
    }
    const yearItems = [...distributions.year.recallStatus, ...distributions.year.recallCombination];
    const yearDomain = computeDistributionDomain(yearItems, "linear");
    const yearFormat = (value) => Math.round(value).toString();

    const sizeItems = [...distributions.sampleSize.recallStatus, ...distributions.sampleSize.recallCombination];
    const sizeDomain = computeDistributionDomain(sizeItems, "log");
    const sizeFormat = (value) => number(Math.round(value));

    const citationItems = [...distributions.citationsPerYear.recallStatus, ...distributions.citationsPerYear.recallCombination];
    const citationDomain = computeDistributionDomain(citationItems, "log");
    const citationFormat = (value) => (value < 10 ? value.toFixed(1) : number(Math.round(value)));

    const countItems = [...distributions.citationCount.recallStatus, ...distributions.citationCount.recallCombination];
    const countDomain = computeDistributionDomain(countItems, "log");
    const countFormat = (value) => number(Math.round(value));

    return `
      <section class="panel cross-summary-section" aria-labelledby="characteristics-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="characteristics-summary-title">Study characteristics by recall pattern</h2>
            <p>
              Publication year (from each review's included RIS export), sample size
              (Cochrane's own analyzed N: the largest Experimental N + Control N across a
              study's analysis rows), citations per year (Semantic Scholar citation count
              divided by years since publication, so a study isn't penalized just for
              being too new to have accumulated citations yet), and total citations (the
              same Semantic Scholar count, unnormalized - shown alongside citations per
              year rather than instead of it, since a raw count is confounded with a
              study's age), compared for studies no chatbot ever recalled versus studies
              recalled by at least one, and for the exact combination of chatbot(s) that
              recalled each study. Recall-combination groups are mutually exclusive - each
              recalled study belongs to exactly one of them - unlike a per-chatbot "did
              this chatbot recall it at least once" grouping, which would count a study
              recalled by multiple chatbots in each of their groups. "Gemini only" and
              "Claude+Gemini" are omitted here since each has only one study in the current
              data; those two studies remain in the "recalled vs. not" comparison above.
              Boxes show the interquartile range with a median line; whiskers extend to the
              most extreme value within 1.5x the IQR; dots beyond the whiskers are
              outliers. Each small dot is one study, jittered vertically only for
              visibility.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderDistributionCard("Publication year — recalled vs. not", "linear", yearDomain, yearFormat, distributions.year.recallStatus, distributions.year.recallStatusTest)}
          ${renderDistributionCard("Publication year — by recall combination", "linear", yearDomain, yearFormat, distributions.year.recallCombination, distributions.year.recallCombinationTest, distributions.year.recallCombinationPosthoc)}
          ${renderDistributionCard("Sample size — recalled vs. not (log scale)", "log", sizeDomain, sizeFormat, distributions.sampleSize.recallStatus, distributions.sampleSize.recallStatusTest)}
          ${renderDistributionCard("Sample size — by recall combination (log scale)", "log", sizeDomain, sizeFormat, distributions.sampleSize.recallCombination, distributions.sampleSize.recallCombinationTest, distributions.sampleSize.recallCombinationPosthoc)}
          ${renderDistributionCard("Citations per year — recalled vs. not (log scale)", "log", citationDomain, citationFormat, distributions.citationsPerYear.recallStatus, distributions.citationsPerYear.recallStatusTest)}
          ${renderDistributionCard("Citations per year — by recall combination (log scale)", "log", citationDomain, citationFormat, distributions.citationsPerYear.recallCombination, distributions.citationsPerYear.recallCombinationTest, distributions.citationsPerYear.recallCombinationPosthoc)}
          ${renderDistributionCard("Total citations — recalled vs. not (log scale)", "log", countDomain, countFormat, distributions.citationCount.recallStatus, distributions.citationCount.recallStatusTest)}
          ${renderDistributionCard("Total citations — by recall combination (log scale)", "log", countDomain, countFormat, distributions.citationCount.recallCombination, distributions.citationCount.recallCombinationTest, distributions.citationCount.recallCombinationPosthoc)}
        </div>
      </section>
    `;
  }

  function renderOpenAccessTestDetail(test) {
    if (test.method === "Chi-square test of independence") {
      const groupSummary = test.groupLabels
        .map((label, index) => `${label} n=${number(test.totals[index])}`)
        .join(", ");
      return `${text(test.method)}, ${text(groupSummary)}, df=${number(test.degreesOfFreedom)} · p${permutationPValue(test.pValue)}`;
    }
    return `${text(test.method)}, ${text(test.comparisonLabel)} (n=${number(test.totalA)} vs. n=${number(test.totalB)}) · p${permutationPValue(test.pValue)}`;
  }

  function renderFisherPosthocTable(posthoc) {
    if (!Array.isArray(posthoc) || !posthoc.length) {
      return "";
    }
    const rows = posthoc.map((comparison) => `
      <tr>
        <th scope="row">${text(comparison.groupLabelA)} vs. ${text(comparison.groupLabelB)}</th>
        <td>${precisePercent(comparison.rateA)}</td>
        <td>${precisePercent(comparison.rateB)}</td>
        <td>${permutationPValue(comparison.pValueRaw)}</td>
        <td>${permutationPValue(comparison.pValueBonferroni)}${text(significanceStars(comparison.pValueBonferroni))}</td>
      </tr>
    `).join("");
    return `
      <div class="summary-table-wrap posthoc-wrap">
        <table class="summary-table logistic-regression-table posthoc-table">
          <thead>
            <tr>
              <th scope="col">Pairwise comparison (Fisher's exact)</th>
              <th scope="col">Rate A</th>
              <th scope="col">Rate B</th>
              <th scope="col">Raw p</th>
              <th scope="col">Bonferroni p</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function renderRateBarRow(item) {
    return `
      <div class="distribution-row">
        <div class="distribution-row-label">
          <strong>${text(item.label)}</strong>
          <small>${number(item.openCount)}/${number(item.total)} (${precisePercent(item.rate)})</small>
        </div>
        <span class="rate-bar-track" aria-hidden="true">
          <span
            class="rate-bar-fill"
            data-group-id="${text(item.groupId)}"
            style="width: ${(item.rate * 100).toFixed(2)}%"
          ></span>
        </span>
      </div>
    `;
  }

  function renderRateCard(title, items, test, posthoc) {
    const rows = items.map(renderRateBarRow).join("");
    const testMarkup = test ? `
      <div class="summary-test">
        <span>Difference at p&lt;0.05 <strong>${test.significantAt05 ? "Yes" : "No"}</strong></span>
        <small>${renderOpenAccessTestDetail(test)}</small>
      </div>
    ` : "";
    const posthocMarkup = posthoc ? renderFisherPosthocTable(posthoc) : "";
    return `
      <article class="summary-dimension distribution-card">
        <h3>${text(title)}</h3>
        <div class="distribution-rows">
          ${rows}
        </div>
        ${testMarkup}
        ${posthocMarkup}
      </article>
    `;
  }

  function renderOpenAccessDistribution() {
    const openAccess = activeExperiment.openAccessDistribution;
    if (!openAccess) {
      return "";
    }
    return `
      <section class="panel cross-summary-section" aria-labelledby="open-access-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="open-access-summary-title">Open access by recall pattern</h2>
            <p>
              Semantic Scholar's open-access flag for the same best-matched PMID used for
              citation counts, compared for studies no chatbot ever recalled versus studies
              recalled by at least one, and for the exact combination of chatbot(s) that
              recalled each study (same recall-combination groups as above). Unlike the
              four characteristics above, this is binary, so each group is shown as a rate
              rather than a box plot: the two-group comparison uses Fisher's exact test, and
              the five-group comparison uses a chi-square test of independence as the
              omnibus test, followed by Bonferroni-adjusted pairwise Fisher's exact tests.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderRateCard("Open access — recalled vs. not", openAccess.recallStatus, openAccess.recallStatusTest)}
          ${renderRateCard("Open access — by recall combination", openAccess.recallCombination, openAccess.recallCombinationTest, openAccess.recallCombinationPosthoc)}
        </div>
      </section>
    `;
  }

  function renderRoleCharacteristicDistributions() {
    const distributions = activeExperiment.roleCharacteristicDistributions;
    if (!distributions) {
      return "";
    }
    const yearItems = distributions.year.recallCombination;
    const yearDomain = computeDistributionDomain(yearItems, "linear");
    const yearFormat = (value) => Math.round(value).toString();

    const sizeItems = distributions.sampleSize.recallCombination;
    const sizeDomain = computeDistributionDomain(sizeItems, "log");
    const sizeFormat = (value) => number(Math.round(value));

    const citationItems = distributions.citationsPerYear.recallCombination;
    const citationDomain = computeDistributionDomain(citationItems, "log");
    const citationFormat = (value) => (value < 10 ? value.toFixed(1) : number(Math.round(value)));

    const countItems = distributions.citationCount.recallCombination;
    const countDomain = computeDistributionDomain(countItems, "log");
    const countFormat = (value) => number(Math.round(value));

    return `
      <section class="panel cross-summary-section" aria-labelledby="role-characteristics-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="role-characteristics-summary-title">Study characteristics by recall pattern (user role)</h2>
            <p>
              The same four characteristics as "Study characteristics by recall pattern"
              above (publication year, sample size, citations per year, total citations),
              now compared for the exact combination of user role(s) - patient, clinician,
              researcher - that recalled each study, aggregated across all three chatbots.
              Recall-combination groups are mutually exclusive, same as the chatbot version.
              "Patient only" (2 studies), "Clinician only" (3), and "Patient+Clinician" (1)
              are omitted here since each falls below the four-study floor used for the
              chatbot combinations' smallest retained group (Gemini+GPT, n=4); those studies
              remain in the "recalled vs. not" comparison above, which is unchanged by this
              role breakdown since recall status doesn't depend on which dimension groups it.
              Boxes show the interquartile range with a median line; whiskers extend to the
              most extreme value within 1.5x the IQR; dots beyond the whiskers are outliers.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderDistributionCard("Publication year — by role combination", "linear", yearDomain, yearFormat, distributions.year.recallCombination, distributions.year.recallCombinationTest, distributions.year.recallCombinationPosthoc)}
          ${renderDistributionCard("Sample size — by role combination (log scale)", "log", sizeDomain, sizeFormat, distributions.sampleSize.recallCombination, distributions.sampleSize.recallCombinationTest, distributions.sampleSize.recallCombinationPosthoc)}
          ${renderDistributionCard("Citations per year — by role combination (log scale)", "log", citationDomain, citationFormat, distributions.citationsPerYear.recallCombination, distributions.citationsPerYear.recallCombinationTest, distributions.citationsPerYear.recallCombinationPosthoc)}
          ${renderDistributionCard("Total citations — by role combination (log scale)", "log", countDomain, countFormat, distributions.citationCount.recallCombination, distributions.citationCount.recallCombinationTest, distributions.citationCount.recallCombinationPosthoc)}
        </div>
      </section>
    `;
  }

  function renderRoleOpenAccessDistribution() {
    const openAccess = activeExperiment.roleOpenAccessDistribution;
    if (!openAccess) {
      return "";
    }
    return `
      <section class="panel cross-summary-section" aria-labelledby="role-open-access-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="role-open-access-summary-title">Open access by recall pattern (user role)</h2>
            <p>
              The same open-access comparison as "Open access by recall pattern" above, now
              grouped by the exact combination of user role(s) that recalled each study
              (same groups and floor as the role characteristics section above). A
              chi-square test of independence is the omnibus test, followed by
              Bonferroni-adjusted pairwise Fisher's exact tests.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderRateCard("Open access — by role combination", openAccess.recallCombination, openAccess.recallCombinationTest, openAccess.recallCombinationPosthoc)}
        </div>
      </section>
    `;
  }

  function renderRoleUniversalityDistributions() {
    const distributions = activeExperiment.roleUniversalityDistributions;
    if (!distributions) {
      return "";
    }
    const yearDomain = computeDistributionDomain(distributions.year.roleUniversality, "linear");
    const yearFormat = (value) => Math.round(value).toString();

    const sizeDomain = computeDistributionDomain(distributions.sampleSize.roleUniversality, "log");
    const sizeFormat = (value) => number(Math.round(value));

    const citationDomain = computeDistributionDomain(distributions.citationsPerYear.roleUniversality, "log");
    const citationFormat = (value) => (value < 10 ? value.toFixed(1) : number(Math.round(value)));

    const countDomain = computeDistributionDomain(distributions.citationCount.roleUniversality, "log");
    const countFormat = (value) => number(Math.round(value));

    return `
      <section class="panel cross-summary-section" aria-labelledby="role-universality-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="role-universality-summary-title">Study characteristics by role dependence</h2>
            <p>
              The same four characteristics as above, now compared as a plain two-group
              split: "Role-agnostic recall" (all three roles recalled the study) versus
              "Researcher-dependent recall" (the three retained role-combination groups
              above pooled together - Researcher only, Clinician+Researcher, and
              Patient+Researcher - every one of which required a researcher-role
              response to surface the study, since patient and/or clinician missed it).
              Pooling those three groups turns the sparse four-way comparison above into
              a well-powered two-group Mann-Whitney U test, and answers a narrower
              question directly: what distinguishes studies that specifically needed a
              researcher-role response to be found, from studies any role's response finds.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderDistributionCard("Publication year — role-agnostic vs. researcher-dependent", "linear", yearDomain, yearFormat, distributions.year.roleUniversality, distributions.year.roleUniversalityTest)}
          ${renderDistributionCard("Sample size — role-agnostic vs. researcher-dependent (log scale)", "log", sizeDomain, sizeFormat, distributions.sampleSize.roleUniversality, distributions.sampleSize.roleUniversalityTest)}
          ${renderDistributionCard("Citations per year — role-agnostic vs. researcher-dependent (log scale)", "log", citationDomain, citationFormat, distributions.citationsPerYear.roleUniversality, distributions.citationsPerYear.roleUniversalityTest)}
          ${renderDistributionCard("Total citations — role-agnostic vs. researcher-dependent (log scale)", "log", countDomain, countFormat, distributions.citationCount.roleUniversality, distributions.citationCount.roleUniversalityTest)}
        </div>
      </section>
    `;
  }

  function renderRoleUniversalityOpenAccess() {
    const openAccess = activeExperiment.roleUniversalityOpenAccess;
    if (!openAccess) {
      return "";
    }
    return `
      <section class="panel cross-summary-section" aria-labelledby="role-universality-open-access-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="role-universality-open-access-title">Open access by role dependence</h2>
            <p>
              The same open-access comparison as above, grouped by role dependence
              (same two-group split as "Study characteristics by role dependence" above)
              instead of the four-way role combination. Uses Fisher's exact test, the
              same binary-outcome treatment as the "recalled vs. not" open-access
              comparison.
            </p>
          </div>
        </header>
        <div class="summary-dimension-grid distribution-grid">
          ${renderRateCard("Open access — role-agnostic vs. researcher-dependent", openAccess.roleUniversality, openAccess.roleUniversalityTest)}
        </div>
      </section>
    `;
  }

  function computeValueDomain(values, scale) {
    const low = Math.min(...values);
    const high = Math.max(...values);
    if (scale === "log") {
      const positives = values.filter((value) => value > 0);
      const positiveMin = positives.length ? Math.min(...positives) : 1;
      return { min: positiveMin * 0.85, max: high * 1.15 };
    }
    const span = high - low || 1;
    return { min: low - span * 0.06, max: high + span * 0.06 };
  }

  function significanceStars(pValue) {
    if (pValue < 0.001) return "***";
    if (pValue < 0.01) return "**";
    if (pValue < 0.05) return "*";
    if (pValue < 0.1) return ".";
    return "";
  }

  function computeHistogramBinCounts(values, domain, scaleType, binCount) {
    const scaleFn = makeDistributionScale(domain, scaleType);
    const counts = new Array(binCount).fill(0);
    values.forEach((value) => {
      const position = scaleFn(value);
      const bin = Math.max(0, Math.min(binCount - 1, Math.floor((position / 100) * binCount)));
      counts[bin] += 1;
    });
    return counts;
  }

  function findPair(correlations, fieldA, fieldB) {
    return correlations.pairs.find(
      (pair) => (pair.xField === fieldA && pair.yField === fieldB)
        || (pair.xField === fieldB && pair.yField === fieldA)
    );
  }

  function renderDiagonalCell(correlations, variable) {
    const binCount = 14;
    const allValues = correlations.groups.flatMap(
      (group) => correlations.groupedValues[variable.field][group.groupId]
    );
    const scaleType = variable.logScale ? "log" : "linear";
    const domain = computeValueDomain(allValues, scaleType);
    const bars = correlations.groups.map((group) => {
      const groupValues = correlations.groupedValues[variable.field][group.groupId];
      const counts = computeHistogramBinCounts(groupValues, domain, scaleType, binCount);
      const total = groupValues.length || 1;
      const maxProportion = Math.max(...counts.map((count) => count / total));
      const bars = counts.map((count, index) => {
        const heightPercent = maxProportion ? (count / total / maxProportion) * 100 : 0;
        return `
          <div
            class="correlation-hist-bar"
            data-group-id="${text(group.groupId)}"
            style="left: ${((index / binCount) * 100).toFixed(2)}%; width: ${(100 / binCount).toFixed(2)}%; height: ${heightPercent.toFixed(1)}%"
          ></div>
        `;
      }).join("");
      return bars;
    }).join("");
    return `
      <div class="correlation-cell correlation-diagonal-cell">
        <div class="correlation-hist">${bars}</div>
      </div>
    `;
  }

  function renderCorrelationTextCell(correlations, pair) {
    const rows = [
      { label: "Overall", groupId: null, correlation: pair.correlations.overall },
      ...correlations.groups.map((group) => ({
        label: group.label,
        groupId: group.groupId,
        correlation: pair.correlations[group.groupId],
      })),
    ];
    const lines = rows.map(({ label, groupId, correlation }) => `
      <div class="correlation-text-row" data-group-id="${text(groupId || "overall")}">
        ${text(label)}: <strong>${correlation.rho.toFixed(3)}</strong>${text(significanceStars(correlation.pValue))}
      </div>
    `).join("");
    return `<div class="correlation-cell correlation-text-cell">${lines}</div>`;
  }

  function renderScatterCell(correlations, pair, rowVariable, colVariable) {
    // The stored pair always has xField as the earlier-indexed variable; a
    // lower-triangle cell's x-axis is always its column variable, so flip if
    // this cell's column is the pair's y-field.
    const flip = pair.xField !== colVariable.field;
    const xField = flip ? pair.yField : pair.xField;
    const yField = flip ? pair.xField : pair.yField;
    const xLogScale = flip ? pair.yLogScale : pair.xLogScale;
    const yLogScale = flip ? pair.xLogScale : pair.yLogScale;
    const xScaleType = xLogScale ? "log" : "linear";
    const yScaleType = yLogScale ? "log" : "linear";
    const xValues = pair.points.map((point) => (flip ? point.y : point.x));
    const yValues = pair.points.map((point) => (flip ? point.x : point.y));
    const xDomain = computeValueDomain(xValues, xScaleType);
    const yDomain = computeValueDomain(yValues, yScaleType);
    const xScale = makeDistributionScale(xDomain, xScaleType);
    const yScale = makeDistributionScale(yDomain, yScaleType);

    const dots = pair.points.map((point) => {
      const xValue = flip ? point.y : point.x;
      const yValue = flip ? point.x : point.y;
      return `
        <circle
          class="correlation-scatter-dot"
          data-group-id="${text(point.group)}"
          cx="${xScale(xValue).toFixed(2)}"
          cy="${(100 - yScale(yValue)).toFixed(2)}"
          r="1.3"
        ></circle>
      `;
    }).join("");

    return `
      <div class="correlation-cell correlation-scatter-cell">
        <svg
          class="correlation-scatter-plot"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          role="img"
          aria-label="${text(xField)} vs. ${text(yField)} scatter, colored by recall status"
        >
          ${dots}
        </svg>
      </div>
    `;
  }

  function renderGgpairsMatrix(correlations) {
    const variables = correlations.variables;
    const n = variables.length;

    const columnHeaders = variables.map((variable, index) => `
      <div class="correlation-col-header" style="grid-column: ${index + 1}; grid-row: 1;">${text(variable.label)}</div>
    `).join("");
    const rowHeaders = variables.map((variable, index) => `
      <div class="correlation-row-header" style="grid-column: ${n + 1}; grid-row: ${index + 2};">${text(variable.label)}</div>
    `).join("");

    const cells = [];
    for (let row = 0; row < n; row += 1) {
      for (let col = 0; col < n; col += 1) {
        const style = `grid-column: ${col + 1}; grid-row: ${row + 2};`;
        let cellHtml;
        if (row === col) {
          cellHtml = renderDiagonalCell(correlations, variables[row]);
        } else {
          const pair = findPair(correlations, variables[row].field, variables[col].field);
          cellHtml = row > col
            ? renderScatterCell(correlations, pair, variables[row], variables[col])
            : renderCorrelationTextCell(correlations, pair);
        }
        cells.push(`<div style="${style}">${cellHtml}</div>`);
      }
    }

    const legend = correlations.groups.map((group) => `
      <span class="correlation-legend-item">
        <i class="correlation-legend-swatch" data-group-id="${text(group.groupId)}" aria-hidden="true"></i>
        ${text(group.label)} (n=${number(group.n)})
      </span>
    `).join("");

    return `
      <div class="correlation-matrix-wrap">
        <div class="correlation-matrix" style="grid-template-columns: repeat(${n}, minmax(140px, 1fr)) auto; grid-template-rows: auto repeat(${n}, 130px);">
          ${columnHeaders}
          ${rowHeaders}
          ${cells.join("")}
        </div>
      </div>
      <div class="correlation-legend">${legend}</div>
    `;
  }

  function renderPredictorCorrelations() {
    const correlations = activeExperiment.predictorCorrelations;
    if (!correlations) {
      return "";
    }
    return `
      <section class="panel cross-summary-section" aria-labelledby="predictor-correlations-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="predictor-correlations-title">Predictor correlations</h2>
            <p>
              A multicollinearity check for four of the characteristics above (design is
              excluded - it is categorical, not numeric), before treating them as
              independent predictors (e.g. in a multiple logistic regression). Diagonal
              panels show each group's distribution (bars normalized to that group's own
              total, so differing group sizes are comparable); the lower triangle shows
              scatter plots colored by recall status; the upper triangle shows each pair's
              Spearman rank correlation, overall and by group, with significance stars
              (*** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05, . p&lt;0.1) - among the
              ${number(correlations.studyCount)} studies with all four values present.
              Spearman is used because sample size, citations per year, and total
              citations are all heavily right-skewed and rank correlation is invariant to
              the log-scaling used for display.
            </p>
          </div>
        </header>
        ${renderGgpairsMatrix(correlations)}
      </section>
    `;
  }

  function renderLogisticRegressionSection(regression, { titleId, heading, outcomeDescription }) {
    if (!regression || !Array.isArray(regression.rows)) {
      return "";
    }
    const rowMarkup = (row) => `
      <tr>
        <th scope="row">${text(row.label)}</th>
        <td>${row.coefficient.toFixed(4)}</td>
        <td>${row.clusteredStdErr.toFixed(4)}</td>
        <td>${permutationPValue(row.clusteredPValue)}${text(significanceStars(row.clusteredPValue))}</td>
        <td>${permutationPValue(row.naivePValue)}</td>
        <td>${row.oddsRatio.toFixed(3)}</td>
        <td>(${row.oddsRatioCiLow.toFixed(2)}, ${row.oddsRatioCiHigh.toFixed(2)})</td>
        <td>${row.vif.toFixed(2)}</td>
      </tr>
    `;
    const interceptRow = `
      <tr>
        <th scope="row">Intercept</th>
        <td>${regression.intercept.coefficient.toFixed(4)}</td>
        <td>${regression.intercept.clusteredStdErr.toFixed(4)}</td>
        <td>${permutationPValue(regression.intercept.clusteredPValue)}${text(significanceStars(regression.intercept.clusteredPValue))}</td>
        <td>${permutationPValue(regression.intercept.naivePValue)}</td>
        <td>—</td>
        <td>—</td>
        <td>—</td>
      </tr>
    `;
    return `
      <section class="panel cross-summary-section" aria-labelledby="${text(titleId)}">
        <header class="cross-summary-heading">
          <div>
            <h2 id="${text(titleId)}">${text(heading)}</h2>
            <p>
              logit(${outcomeDescription}) ~ year + log(sample size) +
              log(citations per year + ${number(regression.citationsPerYearOffset)}), fit on the
              ${number(regression.n)} studies with all three values present. Standard errors,
              p-values, and significance stars use review-clustered SEs (${number(regression.nClusters)}
              review clusters); the naive p-value column ignores clustering for comparison.
              VIF is the Variance Inflation Factor from this fitted model (well under ~5
              indicates no serious multicollinearity). The intercept's odds ratio and 95% CI
              are not meaningful (they describe year&nbsp;=&nbsp;0) and are shown as "—".
            </p>
          </div>
        </header>
        <div class="summary-table-wrap">
          <table class="summary-table logistic-regression-table">
            <thead>
              <tr>
                <th scope="col">Predictor</th>
                <th scope="col">Coef.</th>
                <th scope="col">Clust. SE</th>
                <th scope="col">Clust. p</th>
                <th scope="col">Naive p</th>
                <th scope="col">Odds ratio</th>
                <th scope="col">95% CI</th>
                <th scope="col">VIF</th>
              </tr>
            </thead>
            <tbody>
              ${interceptRow}
              ${regression.rows.map(rowMarkup).join("")}
            </tbody>
          </table>
        </div>
        <div class="summary-test">
          <span>Pseudo R² (McFadden) <strong>${regression.pseudoRSquared.toFixed(4)}</strong></span>
          <small>Log-likelihood ${regression.logLikelihood.toFixed(2)} · likelihood-ratio test vs. null model p${permutationPValue(regression.llrPValue)}</small>
        </div>
      </section>
    `;
  }

  function renderLogisticRegressionTable() {
    return renderLogisticRegressionSection(activeExperiment.logisticRegression, {
      titleId: "logistic-regression-title",
      heading: "Multiple logistic regression on recall",
      outcomeDescription: "P(recalled by at least one chatbot)",
    });
  }

  function renderRoleUniversalityLogisticRegressionTable() {
    return renderLogisticRegressionSection(activeExperiment.roleUniversalityLogisticRegression, {
      titleId: "role-universality-logistic-regression-title",
      heading: "Multiple logistic regression on role dependence",
      outcomeDescription: "P(researcher-dependent recall, vs. role-agnostic recall)",
    });
  }

  function renderCitationIssueExample(example) {
    if (!example) {
      return "—";
    }
    return `
      <div class="citation-issue-example">
        <div class="citation-issue-example-quote">"${text(example.reportedCitation)}"</div>
        <div class="citation-issue-example-note">
          → resolves to <strong>${text(example.resolvedStudyLabel)}</strong>: ${text(example.notes)}
        </div>
      </div>
    `;
  }

  function renderCitationIssueGroupTable(title, firstColumnLabel, rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      return "";
    }
    return `
      <article class="summary-dimension citation-issue-breakdown">
        <h3>${text(title)}</h3>
        <div class="summary-table-wrap">
          <table class="summary-table logistic-regression-table citation-issue-rate-table">
            <thead>
              <tr>
                <th scope="col">${text(firstColumnLabel)}</th>
                <th scope="col">Flagged rows</th>
                <th scope="col">Response-study rows</th>
                <th scope="col">Row rate</th>
                <th scope="col">Affected answers</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((row) => `
                <tr>
                  <th scope="row">${text(row.label)}</th>
                  <td>${number(row.flaggedCount)}</td>
                  <td>${number(row.matchedCount)}</td>
                  <td>${precisePercent(row.rate)}</td>
                  <td>${number(row.affectedAnswerCount)}/${number(row.answerCount)} (${precisePercent(row.answerRate)})</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </article>
    `;
  }

  function renderCitationIssueModelRoleMatrix(items) {
    if (!Array.isArray(items) || items.length === 0) {
      return "";
    }
    const modelRows = Array.from(
      new Map(items.map((item) => [item.model, item.modelLabel || item.model])).entries()
    );
    const roleColumns = Array.from(
      new Map(items.map((item) => [item.roleId, item.roleLabel || item.roleId])).entries()
    );
    const itemByKey = new Map(items.map((item) => [`${item.model}|${item.roleId}`, item]));
    return `
      <article class="summary-dimension citation-issue-model-role">
        <h3>Chatbot x user role</h3>
        <div class="summary-table-wrap">
          <table class="summary-table logistic-regression-table citation-issue-matrix-table">
            <thead>
              <tr>
                <th scope="col">Chatbot</th>
                ${roleColumns.map(([, label]) => `<th scope="col">${text(label)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${modelRows.map(([model, modelLabel]) => `
                <tr>
                  <th scope="row">${text(modelLabel)}</th>
                  ${roleColumns.map(([roleId]) => {
                    const item = itemByKey.get(`${model}|${roleId}`);
                    if (!item) {
                      return "<td>—</td>";
                    }
                    return `
                      <td>
                        <strong>${precisePercent(item.rate)}</strong>
                        <small>${number(item.flaggedCount)}/${number(item.matchedCount)} rows · ${number(item.affectedAnswerCount)}/${number(item.answerCount)} answers</small>
                      </td>
                    `;
                  }).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </article>
    `;
  }

  function renderCitationIssueSummary() {
    const summary = activeExperiment.citationIssueSummary;
    if (!summary || !Array.isArray(summary.reviews)) {
      return "";
    }
    const rows = summary.reviews.map((review) => `
      <tr>
        <th scope="row">${text(review.reviewId)}</th>
        <td>${number(review.flaggedCount)}</td>
        <td>${number(review.matchedCount)}</td>
        <td>${precisePercent(review.rate)}</td>
        <td>${renderCitationIssueExample(review.example)}</td>
      </tr>
    `).join("");
    const breakdownMarkup = `
      <div class="summary-dimension-grid citation-issue-breakdown-grid">
        ${renderCitationIssueGroupTable("By chatbot", "Chatbot", summary.byModel)}
        ${renderCitationIssueGroupTable("By user role", "User role", summary.byRole)}
      </div>
      ${renderCitationIssueModelRoleMatrix(summary.byModelRole)}
    `;
    return `
      <section class="panel cross-summary-section" aria-labelledby="citation-issue-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="citation-issue-summary-title">Citation issues by chatbot, role, and review</h2>
            <p>
              A matched citation is flagged when it has conflicting bibliographic
              details - almost always a wrong lead author, year, or journal on a
              study that was otherwise correctly identified by its title, PMID, or
              PMCID (e.g. citing the real "Bakris 2002" trial but naming the wrong
              authors). <strong>This is misattribution, not fabrication</strong> -
              the underlying study is real and was found; only a surrounding detail
              is wrong. A dedicated check of the much rarer case where a citation
              could not be resolved to any real study at all found that 22 of 23
              mapped to real papers or protocols, though several conflated an
              author, comparator, intervention, or source; only one had no
              findable real match (see
              retrieval_bias/README.md, "Citation issues (identity_issue) are not
              fabrication," for the full write-up). This flag is a reporting count
              only - it is not used to filter or exclude any citation from the
              recall, Venn, or regression numbers shown elsewhere in this demo; a
              flagged citation still gets full credit for its underlying study
              everywhere else.
            </p>
          </div>
        </header>
        ${breakdownMarkup}
        <div class="summary-table-wrap">
          <table class="summary-table logistic-regression-table citation-issue-table">
            <thead>
              <tr>
                <th scope="col">Review</th>
                <th scope="col">Flagged</th>
                <th scope="col">Response-study rows</th>
                <th scope="col">Rate</th>
                <th scope="col">Example</th>
              </tr>
            </thead>
            <tbody>
              ${rows}
              <tr>
                <th scope="row">All reviews</th>
                <td>${number(summary.totalFlagged)}</td>
                <td>${number(summary.totalMatched)}</td>
                <td>${precisePercent(summary.overallRate)}</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    `;
  }

  function renderCrossReviewSummary() {
    const dimensions = Array.isArray(activeExperiment.dimensions)
      ? activeExperiment.dimensions
      : [];
    const definitions = activeExperiment.metricDefinitions || {};
    const citationValues = dimensions.flatMap((dimension) =>
      (Array.isArray(dimension.items) ? dimension.items : [])
        .map((item) => Number(item.meanCitationCount))
        .filter(Number.isFinite)
    );
    const citationMaximum = Math.max(0, ...citationValues);
    const citationScaleMaximum = Math.max(5, Math.ceil(citationMaximum / 5) * 5);
    const overallRecall = activeExperiment.overallRecall || {};
    const overallRecallItems = [
      {
        groupId: "overall-included",
        label: "Cochrane included studies",
        ...overallRecall.includedStudies,
      },
      {
        groupId: "overall-excluded",
        label: "Cochrane excluded studies",
        ...overallRecall.excludedStudies,
      },
    ].filter((item) =>
      Number.isFinite(Number(item.meanRecall))
      && Number.isFinite(Number(item.recallSd))
    );
    const overallRecallMarkup = overallRecallItems.length === 2
      ? `
        <article class="summary-dimension overall-recall-summary">
          <h3>Overall recall</h3>
          <p>Mean ± sample SD across ${number(overallRecall.responseCount)} responses.</p>
          <div class="summary-table-wrap">
            <table class="summary-table">
              <thead>
                <tr>
                  <th scope="col">Study set</th>
                  <th class="summary-bar-heading" scope="col">Mean bar <span>0–100%</span></th>
                  <th scope="col">Mean ± SD</th>
                </tr>
              </thead>
              <tbody>
                ${overallRecallItems.map((item) => `
                  <tr>
                    <th scope="row">${text(item.label)}</th>
                    <td class="summary-bar-cell">
                      <span class="summary-bar-track" aria-hidden="true">
                        <span
                          class="summary-bar-fill"
                          data-group-id="${text(item.groupId)}"
                          style="width: ${(Number(item.meanRecall) * 100).toFixed(2)}%"
                        ></span>
                      </span>
                    </td>
                    <td><strong>${precisePercent(item.meanRecall)} ± ${precisePercent(item.recallSd)}</strong></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </article>
      `
      : "";
    return `
      <section class="panel cross-summary-section" aria-labelledby="cross-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="cross-summary-title">Cross-review main effects</h2>
            <p>${number(overview.reviewCount)} reviews · ${number(overview.responseCount)} answers · ${number(overview.answersPerGroup)} answers per chatbot/role group · ${number(overview.includedStudyCount)} included-study labels</p>
          </div>
        </header>
      </section>
      <section class="panel cross-summary-section" aria-labelledby="citation-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="citation-summary-title">Citations per answer</h2>
            <p>${text(definitions.citations)}</p>
          </div>
        </header>
        <div class="summary-dimension-grid">
          ${dimensions.map((dimension) => renderSummaryDimension(dimension, "citations", citationScaleMaximum)).join("")}
        </div>
      </section>
      <section class="panel cross-summary-section" aria-labelledby="recall-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="recall-summary-title">Recall across reviews</h2>
            <p>${text(definitions.recall)}. Overall differences use balanced label permutations within review-specific blocks.</p>
          </div>
        </header>
        ${overallRecallMarkup}
        <div class="summary-dimension-grid">
          ${dimensions.map((dimension) => renderSummaryDimension(dimension, "recall", 1)).join("")}
        </div>
      </section>
      <section class="panel cross-summary-section" aria-labelledby="jaccard-all-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="jaccard-all-summary-title">Replicate consistency — all candidates</h2>
            <p>${text(definitions.jaccardAllCandidates)}</p>
          </div>
        </header>
        <div class="summary-dimension-grid">
          ${dimensions.map((dimension) => renderSummaryDimension(dimension, "jaccardAll", 1)).join("")}
        </div>
      </section>
      <section class="panel cross-summary-section" aria-labelledby="jaccard-included-summary-title">
        <header class="cross-summary-heading">
          <div>
            <h2 id="jaccard-included-summary-title">Replicate consistency — included studies only</h2>
            <p>${text(definitions.jaccardIncludedOnly)}</p>
          </div>
        </header>
        <div class="summary-dimension-grid">
          ${dimensions.map((dimension) => renderSummaryDimension(dimension, "jaccardIncluded", 1)).join("")}
        </div>
      </section>
      ${renderVennSmallMultiples()}
      ${renderCharacteristicDistributions()}
      ${renderOpenAccessDistribution()}
      ${renderPredictorCorrelations()}
      ${renderLogisticRegressionTable()}
      ${renderCitationIssueSummary()}
      ${renderRoleCharacteristicDistributions()}
      ${renderRoleOpenAccessDistribution()}
      ${renderRoleUniversalityDistributions()}
      ${renderRoleUniversalityOpenAccess()}
      ${renderRoleUniversalityLogisticRegressionTable()}
    `;
  }

  function render() {
    if (activeExperiment.viewType === "cross-review") {
      app.innerHTML = renderCrossReviewSummary();
      return;
    }
    const studies = Array.isArray(sections[activeSection]) ? sections[activeSection] : [];
    app.innerHTML = `
      <section class="panel matrix-panel" aria-label="Study retrieval matrix">
        ${renderControls()}
        ${renderMatrix(studies)}
      </section>
      ${renderVennSmallMultiples()}
    `;
  }

  selectExperimentFromHash();

  window.addEventListener("hashchange", selectExperimentFromHash);

  app.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const tab = target.closest("[data-section]");
    if (!tab) {
      return;
    }
    const nextSection = tab.getAttribute("data-section");
    if (nextSection === "included" || nextSection === "excluded") {
      activeSection = nextSection;
      render();
    }
  });
})();
