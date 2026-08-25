window.__ModuleLoader__.load({
  id: "@law-harness/dsh-law-wiki-graph",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
    const React = require("react");
    const h = React.createElement;

    const CSS = `
.lwg-button,.lwg-control{border:1px solid rgba(137,159,203,.35);background:#172132;color:#e8f0ff;border-radius:9px;font:500 12px/1 system-ui;cursor:pointer}.lwg-button{height:32px;border-radius:18px;padding:0 11px;display:inline-flex;align-items:center;gap:7px}.lwg-button:hover,.lwg-control:hover{background:#223149}.lwg-button:disabled,.lwg-control:disabled{opacity:.55;cursor:default}.lwg-badge{min-width:18px;height:18px;border-radius:9px;padding:0 5px;display:grid;place-items:center;background:rgba(77,139,255,.24);color:#a9c7ff;font-size:11px}.lwg-backdrop{position:fixed;inset:0;z-index:10000;background:rgba(3,7,14,.8);backdrop-filter:blur(8px);display:grid;place-items:center;padding:22px}.lwg-modal{width:min(1320px,97vw);height:min(820px,94vh);border:1px solid rgba(130,149,186,.38);border-radius:18px;background:#101722;color:#edf3ff;box-shadow:0 30px 90px rgba(0,0,0,.6);display:flex;flex-direction:column;overflow:hidden}.lwg-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:18px 20px 14px;border-bottom:1px solid rgba(125,144,180,.18)}.lwg-title{margin:0;font:650 20px/1.25 system-ui}.lwg-sub{margin:5px 0 0;color:#91a2be;font:12px/1.45 system-ui}.lwg-actions,.lwg-toolbar,.lwg-filters{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.lwg-control{height:30px;padding:0 10px}.lwg-body{min-height:0;flex:1;display:grid;grid-template-columns:minmax(0,1fr) 310px}.lwg-main{min-width:0;min-height:0;display:flex;flex-direction:column;background:radial-gradient(circle at 15% 45%,rgba(52,104,205,.14),transparent 34%),linear-gradient(#101722,#0b111b)}.lwg-toolbar{padding:10px 12px;border-bottom:1px solid rgba(125,144,180,.15)}.lwg-search,.lwg-select{height:30px;box-sizing:border-box;border:1px solid rgba(137,159,203,.3);border-radius:8px;background:#121c2b;color:#eaf1ff;padding:0 9px;font:12px system-ui}.lwg-search{min-width:210px;flex:1}.lwg-select{max-width:148px}.lwg-toggle{display:inline-flex;align-items:center;gap:5px;color:#b8c6dc;font:12px system-ui;white-space:nowrap}.lwg-canvas{position:relative;min-height:0;flex:1}.lwg-svg{width:100%;height:100%;display:block;touch-action:none;cursor:grab}.lwg-svg:active{cursor:grabbing}.lwg-edge{stroke:#586984;stroke-width:1.1;opacity:.35;fill:none}.lwg-edge-references{stroke-dasharray:5 5;opacity:.27}.lwg-edge-sources{stroke:#ceac67;stroke-dasharray:2 5}.lwg-edge-used{stroke:#68a7ff;opacity:.92;filter:drop-shadow(0 0 4px #438cf0)}.lwg-node{cursor:pointer}.lwg-node text{font-family:system-ui;pointer-events:none}.lwg-node-used .lwg-shape{filter:drop-shadow(0 0 8px #438cf0)}.lwg-node-selected .lwg-shape{stroke:#fff3a1!important;stroke-width:2.5!important;filter:drop-shadow(0 0 9px #f3c95e)}.lwg-side{border-left:1px solid rgba(125,144,180,.18);padding:15px;overflow:auto;background:#0d141e}.lwg-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:13px}.lwg-stat{border:1px solid rgba(119,145,190,.2);border-radius:9px;background:#141e2c;padding:8px}.lwg-num{display:block;color:#fff;font:650 18px/1.1 system-ui}.lwg-label{display:block;margin-top:3px;color:#8496b4;font:10px/1.3 system-ui}.lwg-side-title{margin:13px 0 7px;color:#dce8fb;font:650 12px/1.2 system-ui}.lwg-detail{border:1px solid rgba(117,145,192,.22);border-radius:10px;background:#131d2a;padding:10px;word-break:break-word}.lwg-detail strong{display:block;font:650 13px/1.35 system-ui}.lwg-detail p,.lwg-detail div{margin:5px 0;color:#a3b3cc;font:11px/1.42 system-ui}.lwg-chip{display:inline-block;margin:3px 4px 0 0;padding:3px 6px;border-radius:9px;background:#1c2b40;color:#bad3fc;font:10px/1.2 system-ui}.lwg-result{display:block;width:100%;text-align:left;border:0;border-top:1px solid rgba(117,145,192,.14);background:none;color:#b8c8e1;padding:8px 1px;cursor:pointer;font:11px/1.35 system-ui}.lwg-result:hover{color:#fff}.lwg-result b{display:block;color:#e5eefc;font:600 12px/1.25 system-ui}.lwg-empty,.lwg-error{position:absolute;inset:0;display:grid;place-items:center;color:#92a2bd;font:14px system-ui}.lwg-error{color:#ff9fa9}.lwg-readonly{color:#79d6ac}.lwg-readonly:before{content:'●';font-size:10px;margin-right:5px}@media(max-width:900px){.lwg-backdrop{padding:6px}.lwg-modal{width:100%;height:97vh}.lwg-body{grid-template-columns:1fr}.lwg-side{display:none}.lwg-title{font-size:17px}.lwg-search{min-width:150px}}
`;

    function installCss() {
      const id = "@law-harness/dsh-law-wiki-graph/main.css";
      if (document.querySelector(`style[data-plugin-css="${id}"]`)) return;
      const tag = document.createElement("style");
      tag.dataset.pluginCss = id;
      tag.textContent = CSS;
      document.head.appendChild(tag);
    }

    function graphUrl(sessionId) {
      const origin = globalThis.location?.origin && globalThis.location.origin !== "null" ? globalThis.location.origin : "http://dsh.internal";
      const url = new URL("/api/law-wiki-graph", origin);
      if (sessionId) url.searchParams.set("sessionId", String(sessionId));
      return url;
    }

    function hashColour(value) {
      const colours = ["#4279be", "#9a6fc1", "#398f83", "#b27648", "#a65172", "#657dbc"];
      return colours[[...String(value || "concept")].reduce((total, char) => total + char.charCodeAt(0), 0) % colours.length];
    }

    function shorten(value, length = 26) {
      return value?.length > length ? `${value.slice(0, length - 1)}…` : value || "未命名";
    }

    function layout(graph) {
      const nodes = graph?.nodes || [];
      const placed = new Map();
      const root = nodes.find((node) => node.type === "root");
      const groups = nodes.filter((node) => node.type === "group");
      const pages = nodes.filter((node) => node.type === "page");
      if (root) placed.set(root.id, { ...root, x: 500, y: 340 });
      groups.forEach((group, index) => {
        const angle = (Math.PI * 2 * index / Math.max(1, groups.length)) - Math.PI / 2;
        placed.set(group.id, { ...group, x: 500 + Math.cos(angle) * 175, y: 340 + Math.sin(angle) * 175 });
      });
      for (const group of groups) {
        const parent = placed.get(group.id);
        const children = pages.filter((page) => page.group === group.label);
        children.forEach((page, index) => {
          const angle = Math.atan2(parent.y - 340, parent.x - 500) + ((index - (children.length - 1) / 2) * 0.48);
          placed.set(page.id, { ...page, x: parent.x + Math.cos(angle) * 115, y: parent.y + Math.sin(angle) * 115 });
        });
      }
      return placed;
    }

    function matchingPages(graph, query, type, trust, usedOnly) {
      const normalized = query.trim().toLocaleLowerCase();
      return (graph?.nodes || []).filter((node) => node.type === "page" && (!normalized || [node.label, node.path, node.description, node.conceptType, ...(node.tags || []), ...(node.jurisdictions || [])].filter(Boolean).join(" ").toLocaleLowerCase().includes(normalized)) && (!type || node.conceptType === type) && (!trust || node.trust === trust) && (!usedOnly || node.usage > 0));
    }

    function GraphView({ graph, selectedId, setSelectedId, filters, focus, zoom, setZoom }) {
      const placed = React.useMemo(() => layout(graph), [graph]);
      const [pan, setPan] = React.useState({ x: 0, y: 0 });
      const drag = React.useRef(null);
      const matches = React.useMemo(() => matchingPages(graph, filters.query, filters.type, filters.trust, filters.usedOnly), [graph, filters]);
      const matchIds = new Set(matches.map((node) => node.id));
      const adjacent = new Set([selectedId]);
      if (focus && selectedId) for (const edge of graph.edges || []) if (edge.source === selectedId || edge.target === selectedId) { adjacent.add(edge.source); adjacent.add(edge.target); }
      const visible = new Set();
      for (const node of graph.nodes || []) {
        if (node.type !== "page" || (matchIds.has(node.id) && (!focus || adjacent.has(node.id)))) visible.add(node.id);
      }
      for (const edge of graph.edges || []) if (visible.has(edge.source) && visible.has(edge.target)) { visible.add(edge.source); visible.add(edge.target); }
      const move = (event) => {
        if (!drag.current) return;
        setPan((current) => ({ x: current.x + event.clientX - drag.current.x, y: current.y + event.clientY - drag.current.y }));
        drag.current = { x: event.clientX, y: event.clientY };
      };
      const elements = [];
      for (const edge of graph.edges || []) {
        if (!visible.has(edge.source) || !visible.has(edge.target)) continue;
        const source = placed.get(edge.source); const target = placed.get(edge.target);
        if (!source || !target) continue;
        const used = Number(edge.usage || 0);
        const midX = (source.x + target.x) / 2; const d = `M ${source.x} ${source.y} Q ${midX} ${(source.y + target.y) / 2 - 16} ${target.x} ${target.y}`;
        elements.push(h("path", { key: edge.id, d, className: `lwg-edge lwg-edge-${edge.type} ${used ? "lwg-edge-used" : ""}`, style: { strokeWidth: 1 + Math.min(4, Math.log2(1 + used) * 1.4) }, onClick: () => setSelectedId(edge.source) }, h("title", null, `${edge.type} · 会话读取 ${used} 次`)));
      }
      for (const node of placed.values()) {
        if (!visible.has(node.id)) continue;
        const used = Number(node.usage || 0); const isPage = node.type === "page"; const isSelected = node.id === selectedId;
        const fill = isPage ? hashColour(node.conceptType) : node.type === "root" ? "#203e68" : "#263852";
        const opacity = isPage && node.status === "deprecated" ? .45 : .95;
        const shape = isPage ? h("rect", { className: "lwg-shape", x: node.x - 15, y: node.y - 9, width: 30, height: 18, rx: 5, fill, fillOpacity: opacity, stroke: used ? "#8cbdff" : "#7184a0", strokeWidth: used ? 1.8 : 1.1 }) : h("circle", { className: "lwg-shape", cx: node.x, cy: node.y, r: node.type === "root" ? 25 : 17, fill, stroke: "#8093b0", strokeWidth: 1.2 });
        elements.push(h("g", { key: node.id, className: `lwg-node ${used ? "lwg-node-used" : ""} ${isSelected ? "lwg-node-selected" : ""}`, onClick: (event) => { event.stopPropagation(); setSelectedId(node.id); } }, shape, h("text", { x: isPage ? node.x + 20 : node.x, y: isPage ? node.y + 4 : node.y + 31, textAnchor: isPage ? "start" : "middle", fill: "#cbd8eb", fontSize: isPage ? 10 : 11, fontWeight: isSelected ? 700 : 500 }, shorten(node.label)), used ? h("text", { x: node.x, y: node.y + 3, textAnchor: "middle", fill: "#fff", fontSize: 8, fontWeight: 800 }, `×${used}`) : null, h("title", null, `${node.label}${node.conceptId ? `\n${node.conceptId}` : ""}`)));
      }
      return h("svg", { className: "lwg-svg", viewBox: "0 0 1000 700", role: "img", "aria-label": "本地法务 OKF 知识图谱", onPointerDown: (event) => { drag.current = { x: event.clientX, y: event.clientY }; }, onPointerMove: move, onPointerUp: () => { drag.current = null; }, onPointerLeave: () => { drag.current = null; }, onWheel: (event) => { event.preventDefault(); setZoom((current) => Math.max(.55, Math.min(2.2, current + (event.deltaY < 0 ? .12 : -.12)))); }, onClick: () => setSelectedId("") }, h("g", { transform: `translate(${pan.x} ${pan.y}) scale(${zoom})` }, elements));
    }

    function Detail({ node }) {
      if (!node) return h("div", { className: "lwg-detail" }, h("strong", null, "选择一个概念"), h("p", null, "点击节点查看 OKF 类型、状态、信任信号、法域与来源登记。"));
      if (node.type !== "page") return h("div", { className: "lwg-detail" }, h("strong", null, node.label), h("p", null, "结构节点；可选择相连的具体概念。"));
      return h("div", { className: "lwg-detail" }, h("strong", null, node.label), h("p", null, node.conceptId), h("div", null, node.conceptType || "未声明类型", " · ", node.status || "stable", " · ", node.trust || "unverified"), node.description ? h("p", null, node.description) : null, (node.tags || []).map((tag) => h("span", { className: "lwg-chip", key: tag }, tag)), (node.jurisdictions || []).length ? h("p", null, "法域：", node.jurisdictions.join(" · ")) : null, h("p", null, `本会话成功读取：${node.usage || 0} 次`), (node.sourceResources || []).length ? h("p", null, "已登记来源：", node.sourceResources.join(" · ")) : h("p", null, "未登记外部来源。"));
    }

    function Modal({ sessionId, graph, loading, error, onRefresh, onClose }) {
      const [filters, setFilters] = React.useState({ query: "", type: "", trust: "", usedOnly: false });
      const [selectedId, setSelectedId] = React.useState("");
      const [focus, setFocus] = React.useState(false);
      const [zoom, setZoom] = React.useState(1);
      React.useEffect(() => { const close = (event) => event.key === "Escape" && onClose(); document.addEventListener("keydown", close); return () => document.removeEventListener("keydown", close); }, [onClose]);
      const pages = (graph?.nodes || []).filter((node) => node.type === "page");
      const types = [...new Set(pages.map((node) => node.conceptType).filter(Boolean))].sort();
      const results = matchingPages(graph, filters.query, filters.type, filters.trust, filters.usedOnly).slice(0, 12);
      const selected = (graph?.nodes || []).find((node) => node.id === selectedId);
      return h("div", { className: "lwg-backdrop", onMouseDown: (event) => event.target === event.currentTarget && onClose() }, h("section", { className: "lwg-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "lwg-title" },
        h("header", { className: "lwg-head" }, h("div", null, h("h2", { id: "lwg-title", className: "lwg-title" }, "法务 OKF 知识图谱"), h("p", { className: "lwg-sub" }, h("span", { className: "lwg-readonly" }, "只读"), " · 节点按 OKF 元数据着色；虚线为概念链接，金色虚线为包内来源关系。拖拽平移、滚轮缩放。")), h("div", { className: "lwg-actions" }, h("button", { className: "lwg-control", type: "button", onClick: onRefresh, disabled: loading }, loading ? "刷新中…" : "刷新"), h("button", { className: "lwg-control", type: "button", onClick: onClose }, "关闭"))),
        h("div", { className: "lwg-body" }, h("main", { className: "lwg-main" }, h("div", { className: "lwg-toolbar" }, h("input", { className: "lwg-search", value: filters.query, placeholder: "搜索标题、概念 ID、标签或法域", onChange: (event) => setFilters({ ...filters, query: event.target.value }) }), h("select", { className: "lwg-select", value: filters.type, onChange: (event) => setFilters({ ...filters, type: event.target.value }) }, h("option", { value: "" }, "所有类型"), types.map((type) => h("option", { key: type, value: type }, type))), h("select", { className: "lwg-select", value: filters.trust, onChange: (event) => setFilters({ ...filters, trust: event.target.value }) }, h("option", { value: "" }, "所有信任状态"), h("option", { value: "unverified" }, "未核验"), h("option", { value: "machine-confirmed" }, "机器确认"), h("option", { value: "human-reviewed" }, "人工复核")), h("label", { className: "lwg-toggle" }, h("input", { type: "checkbox", checked: filters.usedOnly, onChange: (event) => setFilters({ ...filters, usedOnly: event.target.checked }) }), "仅本会话已读"), h("label", { className: "lwg-toggle" }, h("input", { type: "checkbox", checked: focus, onChange: (event) => setFocus(event.target.checked), disabled: !selectedId }), "聚焦相邻节点"), h("button", { className: "lwg-control", type: "button", onClick: () => setZoom(1) }, "重置缩放")), h("div", { className: "lwg-canvas" }, loading && !graph ? h("div", { className: "lwg-empty" }, "正在生成图谱…") : error ? h("div", { className: "lwg-error" }, error) : graph ? h(GraphView, { graph, selectedId, setSelectedId, filters, focus, zoom, setZoom }) : null)),
          h("aside", { className: "lwg-side" }, graph ? h(React.Fragment, null, h("div", { className: "lwg-stat-grid" }, [[graph.stats.concepts ?? graph.stats.documents, "OKF 概念"], [graph.stats.edges, "图谱关系"], [graph.stats.usedDocuments, "会话命中"], [graph.stats.totalReads, "成功读取"]].map(([value, label]) => h("div", { className: "lwg-stat", key: label }, h("span", { className: "lwg-num" }, value), h("span", { className: "lwg-label" }, label)))), h("h3", { className: "lwg-side-title" }, "概念详情"), h(Detail, { node: selected }), h("h3", { className: "lwg-side-title" }, `筛选结果 (${results.length})`), results.map((node) => h("button", { className: "lwg-result", key: node.id, type: "button", onClick: () => setSelectedId(node.id) }, h("b", null, node.label), node.conceptId, " · ", node.trust || "unverified"))) : null))));
    }

    // This component deliberately renders its trigger before the background
    // graph request finishes. The header utility is navigation chrome, not a
    // reward for a completed Wiki tool call.
    function WikiGraphHeaderAction({ sessionId }) {
      const [open, setOpen] = React.useState(false); const [graph, setGraph] = React.useState(null); const [loading, setLoading] = React.useState(false); const [error, setError] = React.useState("");
      const load = React.useCallback(async () => { setLoading(true); setError(""); try { const response = await fetch(graphUrl(sessionId), { headers: { accept: "application/json" } }); if (!response.ok) throw new Error(`图谱接口返回 HTTP ${response.status}`); setGraph(await response.json()); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setLoading(false); } }, [sessionId]);
      React.useEffect(() => { const controller = new AbortController(); fetch(graphUrl(sessionId), { headers: { accept: "application/json" }, signal: controller.signal }).then((response) => response.ok ? response.json() : null).then((value) => value && setGraph(value)).catch(() => {}); return () => controller.abort(); }, [sessionId]);
      return h(React.Fragment, null, h("button", { type: "button", className: "lwg-button", "aria-label": "展开法务 OKF 知识图谱", title: "打开当前会话的 Wiki 图谱", disabled: !sessionId, onClick: () => { setOpen(true); load(); } }, h("span", null, "Wiki 图谱"), h("span", { className: "lwg-badge", title: "当前会话成功读取次数" }, graph?.stats?.totalReads ?? 0)), open ? h(Modal, { sessionId, graph, loading, error, onRefresh: load, onClose: () => setOpen(false) }) : null);
    }

    const inject = ["slots"];
    function apply(ctx) {
      installCss();
      // Session Log uses the same utility slot at its default order (0). A
      // fixed positive order keeps Wiki 图谱 beside it for every live session.
      ctx.slots.inject("conversation.session.header.utilities", () => ctx.slots.register({
        name: "conversation.session.header.utilities",
        id: "law-wiki-graph",
        order: 100,
        label: "Wiki 图谱",
        inject: () => ({})
      }, WikiGraphHeaderAction));
    }
    exports.name = "law-wiki-graph"; exports.inject = inject; exports.apply = apply;
    return module.exports;
  }
});
