// Reusable rules for titles, numeric labels, tables, and multi-metric scenarios.
// These functions encode general rules; scenario examples must not become fixed layouts.

import { addText, HEJIA } from "./hejia_slide_helpers.mjs";

function pt(value) {
  return value * 96 / 72;
}

function numericValue(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new TypeError(`Expected a finite number, received: ${value}`);
  }
  return number;
}

function roundedKey(value, decimals) {
  return numericValue(value).toFixed(decimals);
}

/**
 * Default to one decimal place. Only values that collide when displayed with
 * one decimal are promoted to two decimals; all unaffected values remain at
 * one decimal.
 *
 * Examples:
 * [0.12, 0.13, 0.8] => ["0.12", "0.13", "0.8"]
 * [0.2, 0.3, 0.12, 0.13] => ["0.2", "0.3", "0.12", "0.13"]
 */
export function formatAdaptiveNumbers(values, {
  baseDecimals = 1,
  collisionDecimals = 2,
  suffix = "",
  prefix = "",
} = {}) {
  if (collisionDecimals <= baseDecimals) {
    throw new RangeError("collisionDecimals must be greater than baseDecimals");
  }

  const groups = new Map();
  values.forEach((value, index) => {
    const key = roundedKey(value, baseDecimals);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(index);
  });

  const promoted = new Set();
  for (const indexes of groups.values()) {
    if (indexes.length < 2) continue;
    // Promote only the colliding group. This intentionally also formats exact
    // duplicates consistently, e.g. two displayed 0.1 values become 0.10.
    indexes.forEach((index) => promoted.add(index));
  }

  return values.map((value, index) => {
    const decimals = promoted.has(index) ? collisionDecimals : baseDecimals;
    return `${prefix}${numericValue(value).toFixed(decimals)}${suffix}`;
  });
}

export function buildContentTitle({
  startYear,
  endYear,
  region,
  subject,
  unit,
}) {
  if (!region || !subject) {
    throw new Error("Content title requires both region and subject");
  }
  const yearText = startYear && endYear
    ? `${startYear}-${endYear}年`
    : startYear
      ? `${startYear}年`
      : "";
  return {
    title: `${yearText}${region}${subject}`,
    unit: unit ? `单位：${unit}` : "单位：未提供",
  };
}

/**
 * Add the title and unit in one centered textbox above a chart, table, or
 * long-text block. In an open layout or a single-visual page, use 14 pt for
 * the title and 12 pt for the unit; both lines are bold.
 */
export function addContentBlockTitle(slide, {
  title,
  unit,
  x,
  y,
  width,
  height = 58,
  spacious = true,
  name = "HEJIA_CONTENT_BLOCK_TITLE",
}) {
  if (!title || !unit) {
    throw new Error("Every chart, table, and long-text block requires title and unit");
  }

  const box = addText(slide, `${title}\n${unit}`, x, y, width, height, {
    fontSize: spacious ? 14 : 12,
    color: HEJIA.colors.title,
    bold: false,
    align: "center",
    lineSpacing: 1.2,
    name,
  });
  box.text.typeface = HEJIA.fonts.regular;
  box.text.bold = true;
  box.text.autoFit = "shrinkText";
  box.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };

  const [titleParagraph, unitParagraph] = box.text.paragraphs.items;
  for (const run of titleParagraph?.runs.items ?? []) {
    run.textStyle.bold = true;
    run.textStyle.typeface = HEJIA.fonts.regular;
    run.textStyle.fontSize = pt(spacious ? 14 : 12);
    run.textStyle.color = HEJIA.colors.title;
  }
  for (const run of unitParagraph?.runs.items ?? []) {
    run.textStyle.bold = true;
    run.textStyle.typeface = HEJIA.fonts.regular;
    run.textStyle.fontSize = pt(spacious ? 12 : 10);
    run.textStyle.color = HEJIA.colors.title;
  }
  return box;
}

export function sortEntitiesByMetric(rows, metricKey, direction = "desc") {
  const factor = direction === "asc" ? 1 : -1;
  return [...rows].sort(
    (left, right) => factor * (numericValue(left[metricKey]) - numericValue(right[metricKey])),
  );
}

/**
 * Build a two-level header definition for tables containing metric groups,
 * such as revenue and gross margin, with years/CAGR/YoY beneath each group.
 */
export function buildTwoLevelTableHeader(groups) {
  return groups.map(({ label, columns }) => {
    if (!label || !Array.isArray(columns) || columns.length === 0) {
      throw new Error("Each table header group requires a label and at least one column");
    }
    return {
      topHeader: label,
      span: columns.length,
      subHeaders: columns.map(({ label: subLabel, key }) => ({ label: subLabel, key })),
    };
  });
}

/**
 * Recommend a representation without forcing one fixed layout.
 * The caller remains responsible for selecting the option that best supports
 * the slide's conclusion and available space.
 */
export function recommendMultiMetricPresentation({
  entityCount,
  metricGroups,
  hasSingleYearScaleMetrics = false,
  rankingMetric,
}) {
  const recommendations = [];
  if (hasSingleYearScaleMetrics) {
    recommendations.push("Use sortable bar charts for single-year scale metrics");
  }
  if (entityCount > 1 && rankingMetric) {
    recommendations.push(`Sort entities descending by ${rankingMetric}`);
  }
  if (metricGroups?.length > 1) {
    recommendations.push("Use grouped visuals or a two-level-header table for multi-metric comparison");
  }
  if (entityCount > 8 || metricGroups?.length > 3) {
    recommendations.push("Split the content across slides instead of shrinking labels");
  }
  return recommendations;
}
