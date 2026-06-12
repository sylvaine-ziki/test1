// Reusable editable primitives for fast Hejia-style slide production.
// Positions use a 1280 x 720 canvas.

export const HEJIA = {
  width: 1280,
  height: 720,
  sizes: {
    sourcePt: 10,
  },
  colors: {
    red: "#AD0B29",
    blue: "#085789",
    orange: "#BA650D",
    title: "#404040",
    secondary: "#7F7F7F",
    source: "#919191",
    paper: "#F8F4EC",
    paleRed: "#FDE6EB",
    paleBlue: "#D8EAF6",
    paleOrange: "#F8E9DA",
  },
  fonts: {
    bold: "Source Han Sans CN Bold",
    regular: "思源黑体 CN Regular",
  },
  zones: {
    // Calibrated from the user's 5_浅色图表内容页 master layout.
    storyline: { x: 46.87, y: -0.76, w: 1195.13, h: 122 },
    body: { x: 50, y: 145, w: 1160, h: 515 },
    source: { x: 38.17, y: 673.89, w: 870, h: 32 },
  },
};

function pt(value) {
  return value * 96 / 72;
}

function transparentBox(slide, x, y, w, h, name) {
  return slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height: h },
    fill: { color: "#FFFFFF", transparency: 100000 },
    ...(name ? { name } : {}),
  });
}

export function addText(slide, text, x, y, w, h, {
  fontSize = 12,
  color = HEJIA.colors.title,
  bold = false,
  align = "left",
  lineSpacing = 1.2,
  name,
} = {}) {
  const box = transparentBox(slide, x, y, w, h, name);
  box.text.set(text);
  // artifact-tool uses CSS pixels; convert the SOP's PowerPoint points to px.
  box.text.fontSize = pt(fontSize);
  box.text.typeface = HEJIA.fonts.regular;
  box.text.color = color;
  box.text.bold = bold;
  box.text.alignment = align;
  box.text.verticalAlignment = "middle";
  box.text.autoFit = "shrinkText";
  box.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };
  box.text.lineSpacing = lineSpacing;
  return box;
}

export function addStoryline(slide, {
  secondaryTitle,
  primaryTitle,
}) {
  if (!primaryTitle) {
    throw new Error("Storyline requires one complete primaryTitle sentence; do not split it manually");
  }
  const z = HEJIA.zones.storyline;
  const secondaryBox = addText(slide, secondaryTitle, z.x, z.y, z.w, 44, {
    fontSize: 16,
    color: HEJIA.colors.secondary,
    bold: true,
    lineSpacing: 0.6,
    name: "HEJIA_STORYLINE_SECONDARY",
  });
  secondaryBox.text.typeface = HEJIA.fonts.bold;
  secondaryBox.text.verticalAlignment = "middle";
  secondaryBox.text.autoFit = "shrinkText";
  secondaryBox.text.insets = { left: 9.45, right: 9.45, top: 4.91, bottom: 4.91 };
  const primaryBox = addText(
    slide,
    primaryTitle,
    z.x,
    20.79,
    z.w - 7.5,
    112,
    {
      fontSize: 24,
      color: HEJIA.colors.title,
      bold: true,
      lineSpacing: 1.2,
      name: "HEJIA_STORYLINE_PRIMARY",
    },
  );
  primaryBox.text.verticalAlignment = "middle";
  primaryBox.text.typeface = HEJIA.fonts.bold;
  primaryBox.text.autoFit = "shrinkText";
  primaryBox.text.insets = { left: 9.45, right: 9.45, top: 4.91, bottom: 4.91 };
  return { secondaryBox, primaryBox };
}

export function addSource(slide, sourceText) {
  const z = HEJIA.zones.source;
  const cleanedSource = sourceText
    .replace(/^数据来源[：:]\s*/, "")
    .replace(/[，,]\s*和君咨询分析\s*$/, "");
  const sourceBox = addText(slide, `数据来源：${cleanedSource}，和君咨询分析`, z.x, z.y, z.w, z.h, {
    // Exact PowerPoint size: 10 pt. Do not inherit body or chart-label sizes.
    fontSize: HEJIA.sizes.sourcePt,
    color: HEJIA.colors.source,
    bold: false,
    lineSpacing: 1,
    name: "HEJIA_SOURCE_TEXT",
  });
  sourceBox.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };
  return sourceBox;
}

export function addContentPageFrame(slide, storyline, sourceText) {
  // Keep the imported master background, brand tab, page number, and footer visible.
  addStoryline(slide, storyline);
  addSource(slide, sourceText);
  return HEJIA.zones.body;
}

export function assertInsideBody(position) {
  const b = HEJIA.zones.body;
  if (
    position.left < b.x ||
    position.top < b.y ||
    position.left + position.width > b.x + b.w ||
    position.top + position.height > b.y + b.h
  ) {
    throw new Error(`Body object is outside the Hejia body zone: ${JSON.stringify(position)}`);
  }
}
