window.__ModuleLoader__.load({
  id: "@law-harness/dsh-session-files",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
    const React = require("react");

    const CSS = `
.sf-button{height:32px;border:1px solid var(--dsw-alias-border-l2,#5d6370);border-radius:16px;background:transparent;color:var(--dsw-alias-label-primary,#f5f7fb);padding:4px 10px;display:inline-flex;align-items:center;gap:6px;font:500 13px/20px var(--dsw-font-family,system-ui);cursor:pointer}.sf-button:hover{background:var(--dsw-alias-interactive-bg-hover,rgba(255,255,255,.08))}.sf-button:disabled{opacity:.5;cursor:not-allowed}.sf-count{min-width:17px;height:17px;border-radius:9px;padding:0 4px;display:inline-grid;place-items:center;background:rgba(77,139,255,.2);color:#9bc0ff;font-size:10px}.sf-backdrop{position:fixed;inset:0;z-index:10020;background:rgba(4,7,14,.78);backdrop-filter:blur(8px);display:grid;place-items:center;padding:18px}.sf-modal{width:min(640px,96vw);max-height:min(760px,92vh);border:1px solid rgba(130,149,186,.35);border-radius:18px;background:#111722;color:#edf3ff;box-shadow:0 30px 90px rgba(0,0,0,.55);display:flex;flex-direction:column;overflow:hidden}.sf-head{display:flex;justify-content:space-between;gap:16px;padding:19px 21px 15px;border-bottom:1px solid rgba(125,144,180,.18)}.sf-title{margin:0;font:650 19px/1.3 system-ui}.sf-sub{margin:6px 0 0;color:#91a2bd;font:12px/1.55 system-ui}.sf-close{border:1px solid rgba(140,160,200,.3);border-radius:9px;background:#182131;color:#dce7fb;width:34px;height:34px;cursor:pointer}.sf-body{padding:19px 21px 22px;overflow:auto}.sf-path-row{display:flex;gap:8px}.sf-input{min-width:0;flex:1;border:1px solid #42506a;border-radius:10px;background:#0c131e;color:#fff;padding:10px 11px;font:13px system-ui}.sf-primary{border:0;border-radius:10px;background:#4e83e6;color:#fff;padding:10px 14px;font:600 13px system-ui;cursor:pointer}.sf-primary:disabled{opacity:.55;cursor:not-allowed}.sf-drop{display:grid;place-items:center;text-align:center;min-height:132px;padding:18px;border:1px dashed #4d6285;border-radius:13px;background:#0d1521;cursor:pointer}.sf-drop:hover{border-color:#78a7f7;background:#111d2d}.sf-drop strong{display:block;font:600 14px system-ui}.sf-drop span{display:block;margin-top:7px;color:#8295b4;font:12px/1.5 system-ui}.sf-section-title{margin:20px 0 9px;color:#cbd7ea;font:600 13px system-ui}.sf-list{display:grid;gap:8px}.sf-file{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 11px;border:1px solid rgba(122,148,190,.2);border-radius:10px;background:#141e2c}.sf-file-main{min-width:0}.sf-file-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:550 12px/1.4 system-ui}.sf-file-meta{display:block;margin-top:3px;color:#7f91ad;font:11px/1.35 system-ui}.sf-tag{flex:none;border-radius:9px;background:#1c2b42;color:#94baff;padding:3px 7px;font:10px system-ui}.sf-message{margin-top:11px;padding:9px 10px;border-radius:9px;font:12px/1.5 system-ui}.sf-error{background:rgba(194,67,78,.14);color:#ffabb3}.sf-success{background:rgba(46,172,117,.14);color:#8ee3ba}.sf-warning{margin-top:12px;color:#dfa66c;font:11px/1.55 system-ui}.sf-empty{color:#7487a5;font:12px/1.5 system-ui;padding:7px 0}@media(max-width:640px){.sf-path-row{display:grid}.sf-modal{max-height:96vh}.sf-button{padding:4px 8px}}
`;

    function installCss() {
      const id = "@law-harness/dsh-session-files/main.css";
      if (document.querySelector(`style[data-plugin-css="${id}"]`)) return;
      const tag = document.createElement("style");
      tag.dataset.plugin = "@law-harness/dsh-session-files";
      tag.dataset.pluginCss = id;
      tag.textContent = CSS;
      document.head.appendChild(tag);
    }

    function isLoopback() {
      const hostname = globalThis.location?.hostname || "";
      return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "::1" || hostname === "[::1]";
    }

    function formatBytes(bytes) {
      const value = Number(bytes || 0);
      if (value < 1024) return `${value} B`;
      if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
      return `${(value / 1024 / 1024).toFixed(1)} MB`;
    }

    async function responseJson(response) {
      const value = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(value.message || value.error || `HTTP ${response.status}`);
      return value;
    }

    function appendFileReferences(input, inputActions, files) {
      if (!files.length) return;
      const block = [
        "[会话文件]",
        ...files.map((file) => `- file_id=${file.id}；name=${file.name}；source=${file.source}`),
        "请先调用 session_file_read 读取上述文件，再基于文件内容处理我的问题。"
      ].join("\n");
      const current = String(input?.draft || "");
      inputActions.setDraft(current.trim() ? `${current.trimEnd()}\n\n${block}` : block);
    }

    function SessionFilesModal({ sessionId, input, inputActions, files, setFiles, onClose }) {
      const local = isLoopback();
      const fileInput = React.useRef(null);
      const [localPath, setLocalPath] = React.useState("");
      const [busy, setBusy] = React.useState(false);
      const [message, setMessage] = React.useState("");
      const [error, setError] = React.useState("");

      React.useEffect(() => {
        const close = (event) => event.key === "Escape" && !busy && onClose();
        document.addEventListener("keydown", close);
        return () => document.removeEventListener("keydown", close);
      }, [busy, onClose]);

      async function refresh() {
        const url = new URL("/api/session-files", globalThis.location.origin);
        url.searchParams.set("sessionId", sessionId);
        const payload = await responseJson(await fetch(url, { headers: { accept: "application/json" } }));
        setFiles(payload.files || []);
      }

      async function registerPath(event) {
        event.preventDefault();
        setBusy(true);
        setError("");
        setMessage("");
        try {
          const payload = await responseJson(await fetch("/api/session-files/local-reference", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ sessionId, path: localPath })
          }));
          await refresh();
          appendFileReferences(input, inputActions, [payload.file]);
          setLocalPath("");
          setMessage(`已引用 ${payload.file.name}；文件未复制，Agent 将按原路径只读访问。`);
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : String(reason));
        } finally {
          setBusy(false);
        }
      }

      async function uploadFiles(selected) {
        const candidates = [...(selected || [])];
        if (!candidates.length) return;
        setBusy(true);
        setError("");
        setMessage("");
        const completed = [];
        try {
          for (const file of candidates) {
            const response = await fetch("/api/session-files/upload", {
              method: "POST",
              headers: {
                "content-type": file.type || "application/octet-stream",
                "x-dsh-session-id": sessionId,
                "x-file-name": encodeURIComponent(file.name)
              },
              body: file
            });
            const payload = await responseJson(response);
            completed.push(payload.file);
          }
          await refresh();
          appendFileReferences(input, inputActions, completed);
          setMessage(`已上传 ${completed.length} 个文件到本 Mac 的当前会话 workspace，并加入输入框。`);
        } catch (reason) {
          if (completed.length) {
            await refresh();
            appendFileReferences(input, inputActions, completed);
          }
          setError(`${completed.length ? `已完成 ${completed.length} 个；` : ""}${reason instanceof Error ? reason.message : String(reason)}`);
        } finally {
          if (fileInput.current) fileInput.current.value = "";
          setBusy(false);
        }
      }

      return React.createElement("div", { className: "sf-backdrop", onMouseDown: (event) => event.target === event.currentTarget && !busy && onClose() },
        React.createElement("section", { className: "sf-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "sf-title" },
          React.createElement("header", { className: "sf-head" },
            React.createElement("div", null,
              React.createElement("h2", { id: "sf-title", className: "sf-title" }, local ? "添加本机文件路径" : "上传会话文件"),
              React.createElement("p", { className: "sf-sub" }, local
                ? "只登记绝对路径，不复制文件；处理时由本机 Host 直接只读访问。"
                : "文件会经认证入口写入本 Mac，并按当前对话 Session 隔离。")),
            React.createElement("button", { type: "button", className: "sf-close", disabled: busy, onClick: onClose, "aria-label": "关闭" }, "×")),
          React.createElement("div", { className: "sf-body" },
            local
              ? React.createElement("form", { onSubmit: registerPath, className: "sf-path-row" },
                  React.createElement("input", { className: "sf-input", type: "text", value: localPath, onChange: (event) => setLocalPath(event.target.value), placeholder: "/Users/name/Documents/合同.pdf", disabled: busy, autoFocus: true, "aria-label": "本机文件绝对路径" }),
                  React.createElement("button", { className: "sf-primary", type: "submit", disabled: busy || !localPath.trim() }, busy ? "登记中…" : "引用路径"))
              : React.createElement(React.Fragment, null,
                  React.createElement("input", { ref: fileInput, type: "file", multiple: true, hidden: true, accept: ".txt,.md,.csv,.tsv,.json,.jsonl,.yaml,.yml,.xml,.html,.htm,.log,.pdf,.doc,.docx,.rtf,.odt,.xlsx,.pptx", onChange: (event) => uploadFiles(event.target.files) }),
                  React.createElement("button", { type: "button", className: "sf-drop", disabled: busy, onClick: () => fileInput.current?.click() },
                    React.createElement("div", null,
                      React.createElement("strong", null, busy ? "正在上传到本 Mac…" : "选择一个或多个文档"),
                      React.createElement("span", null, "单文件不超过 25 MB；支持文本、PDF 与常见 Office 文档。")))),
            error ? React.createElement("div", { className: "sf-message sf-error", role: "alert" }, error) : null,
            message ? React.createElement("div", { className: "sf-message sf-success", role: "status" }, message) : null,
            React.createElement("div", { className: "sf-section-title" }, `当前会话文件（${files.length}）`),
            React.createElement("div", { className: "sf-list" }, files.length
              ? files.map((file) => React.createElement("div", { className: "sf-file", key: file.id },
                  React.createElement("div", { className: "sf-file-main" },
                    React.createElement("span", { className: "sf-file-name", title: file.name }, file.name),
                    React.createElement("span", { className: "sf-file-meta" }, `${formatBytes(file.bytes)} · ${file.id}`)),
                  React.createElement("span", { className: "sf-tag" }, file.source === "public-upload" ? "已落盘" : "本机路径")))
              : React.createElement("div", { className: "sf-empty" }, "当前会话尚未添加文件。")),
            React.createElement("p", { className: "sf-warning" }, "不要通过公网入口上传身份证号、未脱敏个人信息、商业秘密或无权处理的第三方材料。上传文件不会自动执行。"))));
    }

    function SessionFilesButton({ sessionId, input, inputActions }) {
      const [open, setOpen] = React.useState(false);
      const [files, setFiles] = React.useState([]);
      React.useEffect(() => {
        if (!sessionId) return;
        const controller = new AbortController();
        const url = new URL("/api/session-files", globalThis.location.origin);
        url.searchParams.set("sessionId", sessionId);
        fetch(url, { headers: { accept: "application/json" }, signal: controller.signal })
          .then((response) => response.ok ? response.json() : null)
          .then((payload) => payload && setFiles(payload.files || []))
          .catch(() => {});
        return () => controller.abort();
      }, [sessionId]);
      return React.createElement(React.Fragment, null,
        React.createElement("button", { type: "button", className: "sf-button", disabled: !sessionId || !inputActions, onClick: () => setOpen(true), "aria-label": isLoopback() ? "添加本机文件路径" : "上传会话文件" },
          React.createElement("span", { "aria-hidden": "true" }, "＋"),
          React.createElement("span", null, "文件"),
          files.length ? React.createElement("span", { className: "sf-count" }, files.length) : null),
        open ? React.createElement(SessionFilesModal, { sessionId, input, inputActions, files, setFiles, onClose: () => setOpen(false) }) : null);
    }

    const inject = ["slots"];
    function apply(ctx) {
      installCss();
      ctx.slots.inject("conversation.input.left", () => ctx.slots.register({
        name: "conversation.input.left",
        id: "session-files",
        order: 25,
        inject: () => ({})
      }, SessionFilesButton));
    }
    exports.name = "session-files";
    exports.inject = inject;
    exports.apply = apply;
    return module.exports;
  }
});
