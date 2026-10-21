async function loadJSON(url) {
  const response = await fetch(url);
  return response.json();
}

function money(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(0)} 万`;
  return value.toFixed(0);
}

function signedMoney(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${money(value)}`;
}

function colorClass(value) {
  return value > 0 ? "up" : value < 0 ? "down" : "";
}

function drawChart(closes) {
  const container = document.getElementById("chart");
  const width = 640;
  const height = 220;
  const pad = 24;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const points = closes.map((close, index) => {
    const x = pad + (index / Math.max(closes.length - 1, 1)) * (width - pad * 2);
    const y = height - pad - ((close - min) / range) * (height - pad * 2);
    return [x, y];
  });
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#243040" />
      <path d="${path}" fill="none" stroke="#4f8cff" stroke-width="3" stroke-linecap="round" />
      ${points.map(([x, y], i) => `<circle cx="${x}" cy="${y}" r="4" fill="#4f8cff"><title>${closes[i]}</title></circle>`).join("")}
    </svg>`;
}

function renderFundFlow(latest) {
  const items = [
    ["主力净流入", latest.main_net],
    ["超大单净流入", latest.super_net],
    ["大单净流入", latest.big_net],
    ["中单净流入", latest.mid_net],
    ["小单净流入", latest.small_net],
  ];
  const max = Math.max(...items.map(([, v]) => Math.abs(v)), 1);
  document.getElementById("fund-flow").innerHTML = items
    .map(([label, value]) => {
      const color = value > 0 ? "var(--up)" : "var(--down)";
      return `
        <div class="flow-row">
          <span>${label}</span>
          <div class="flow-track">
            <div class="flow-bar" style="width:${(Math.abs(value) / max) * 100}%;background:${color}"></div>
          </div>
          <span class="${colorClass(value)}">${signedMoney(value)}</span>
        </div>`;
    })
    .join("");
}

function renderConclusion(latest, closes) {
  let conclusion = "";
  if (latest.main_net >= 0 && latest.mid_net + latest.small_net >= 0) {
    conclusion = "主力与中小单同时净流入，资金面偏积极。";
  } else if (latest.main_net >= 0 && latest.mid_net + latest.small_net < 0) {
    conclusion = "主力净流入、中小单净流出，资金向大单集中。";
  } else if (latest.main_net < 0 && latest.mid_net + latest.small_net >= 0) {
    conclusion = "主力净流出、中小单净流入，需警惕大资金逢高减持。";
  } else {
    conclusion = "主力与中小单同时净流出，资金面偏弱。";
  }
  if (closes.length >= 2) {
    const change = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;
    conclusion += ` 观察期内价格累计 ${change > 0 ? "上涨" : "下跌"} ${Math.abs(change).toFixed(2)}%。`;
  }
  document.getElementById("conclusion").textContent = conclusion;
}

function renderInventory(data) {
  const categories = Object.entries(data.by_category || {})
    .map(([key, value]) => `${key} ${value}`)
    .join(" · ");
  const lines = [`文件总数：${data.total_files ?? "--"}`, `分类：${categories || "--"}`];
  document.getElementById("inventory").innerHTML = lines
    .map((line) => `<div class="inventory-line">${line}</div>`)
    .join("");
}

async function init() {
  const [latest, inventory, log] = await Promise.all([
    loadJSON("/api/latest"),
    loadJSON("/api/inventory"),
    loadJSON("/api/log"),
  ]);

  const items = (latest.items || [])
    .filter((item) => item.data && typeof item.data.close === "number")
    .sort((a, b) => String(a.published).localeCompare(String(b.published)));
  const closes = items.map((item) => item.data.close);
  const stock = items[items.length - 1];

  document.getElementById("update-time").textContent = `数据更新时间：${latest.fetched_at || "--"}`;
  if (stock) {
    const d = stock.data;
    document.getElementById("price").textContent = d.close.toFixed(2);
    document.getElementById("change").textContent =
      d.change_pct === undefined ? "--" : `${d.change_pct >= 0 ? "+" : ""}${d.change_pct.toFixed(2)}%`;
    document.getElementById("change").className = `sub ${colorClass(d.change_pct || 0)}`;
    document.getElementById("main-net").textContent = signedMoney(d.main_net);
    document.getElementById("main-net").className = `money ${colorClass(d.main_net)}`;
    document.getElementById("big-net").textContent = signedMoney(d.super_net + d.big_net);
    document.getElementById("big-net").className = `money ${colorClass(d.super_net + d.big_net)}`;
    document.getElementById("small-net").textContent = signedMoney(d.mid_net + d.small_net);
    document.getElementById("small-net").className = `money ${colorClass(d.mid_net + d.small_net)}`;
    document.getElementById("trend-badge").textContent = d.change_pct >= 0 ? "上涨" : "下跌";
    drawChart(closes);
    renderFundFlow(d);
    renderConclusion(d, closes);
  }

  renderInventory(inventory);
  document.getElementById("log").textContent = log.log || "暂无运行日志";
}

init();
