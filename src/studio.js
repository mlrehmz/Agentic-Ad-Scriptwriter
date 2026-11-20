(() => {
  const byId = (id) => document.getElementById(id);
  const state = {
    brief: null,
    backend: "mock",
    backendLabel: "Mock · offline",
    selected: null,
    script: "",
    draft: null,
    previous: null,
    baseline: null,
    submittedBrief: null,
    comparisonRequest: 0,
    checkRequest: 0,
    flowVersion: 0,
    scriptRequest: 0,
    scriptVersion: 0,
    audioUrl: null,
    audioBlob: null,
  };

  const lines = (id) => byId(id).value.split("\n").map((line) => line.trim()).filter(Boolean);
  const briefFromForm = () => ({
    product_name: byId("name").value,
    description: byId("description").value,
    audience: byId("audience").value,
    benefit: byId("benefit").value,
    tone: byId("tone").value,
    platform: byId("platform").value,
    duration: Number(byId("duration").value),
    cta: byId("cta").value,
    required_points: lines("required"),
    prohibited_claims: lines("prohibited"),
  });

  async function api(route, data) {
    const response = await fetch(`/api/${route}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed.");
    return result;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function visibleScript() {
    return state.draft === null ? state.script : state.draft;
  }

  async function refreshChecks(text) {
    const request = ++state.checkRequest;
    try {
      const result = await api("checks", { brief: state.brief, text });
      if (request !== state.checkRequest) return;
      byId("checks").innerHTML = result.checks.map((check) => `<div>${escapeHtml(check)}</div>`).join("");
    } catch (error) {
      byId("status").textContent = error.message;
    }
  }

  function updateArenaScript() {
    const roomScript = document.querySelector(".room-script");
    if (roomScript) roomScript.textContent = state.script;
  }

  function showAcceptedScript(text, checks = null) {
    state.scriptVersion += 1;
    state.script = text;
    state.draft = null;
    byId("script").value = text;
    byId("script").disabled = false;
    byId("undo").disabled = false;
    byId("accept-rewrite").classList.add("hidden");
    for (const button of document.querySelectorAll("#rewrites [data-action]")) button.disabled = false;
    if (checks) {
      byId("checks").innerHTML = checks.map((check) => `<div>${escapeHtml(check)}</div>`).join("");
    } else {
      refreshChecks(text);
    }
    updateArenaScript();
  }

  function showDraft(text, checks = null) {
    state.scriptRequest += 1;
    state.scriptVersion += 1;
    state.previous = state.script;
    state.draft = text;
    byId("script").value = text;
    byId("script").disabled = false;
    byId("undo").disabled = false;
    byId("accept-rewrite").classList.remove("hidden");
    for (const button of document.querySelectorAll("#rewrites [data-action]")) button.disabled = true;
    if (checks) {
      byId("checks").innerHTML = checks.map((check) => `<div>${escapeHtml(check)}</div>`).join("");
    } else {
      refreshChecks(text);
    }
  }

  async function fillArena(direction) {
    const request = ++state.comparisonRequest;
    if (!state.baseline) {
      const result = await api("baseline", { brief: state.brief, backend: state.backend });
      if (request !== state.comparisonRequest || direction !== state.selected) return;
      state.baseline = result;
    }
    if (request !== state.comparisonRequest || direction !== state.selected) return;
    byId("comparison").innerHTML = `
      <article class="card"><span class="tag">One-prompt baseline · ${escapeHtml(state.baseline.backend)}</span>
        <div class="script">${escapeHtml(state.baseline.script)}</div></article>
      <article class="card"><span class="tag">Writers’ room direction · ${escapeHtml(state.backendLabel)}</span>
        <div class="script room-script">${escapeHtml(state.script)}</div></article>`;
  }

  function chooseDirection(direction, card) {
    state.flowVersion += 1;
    state.scriptRequest += 1;
    state.selected = direction;
    state.previous = null;
    showAcceptedScript(direction.script, direction.checks);
    byId("edit-section").classList.remove("hidden");
    byId("gremlin").classList.remove("hidden");
    byId("arena").classList.remove("hidden");
    byId("campaign").classList.remove("hidden");
    document.querySelectorAll("#directions .route-row").forEach((item) => item.classList.remove("selected"));
    document.querySelectorAll("#directions [data-select]").forEach((button) => button.setAttribute("aria-pressed", "false"));
    card.classList.add("selected");
    card.querySelector("[data-select]").setAttribute("aria-pressed", "true");
    fillArena(direction).catch((error) => { byId("vote-note").textContent = error.message; });
  }

  byId("generate").onclick = async () => {
    const button = byId("generate");
    button.disabled = true;
    state.flowVersion += 1;
    state.scriptRequest += 1;
    state.comparisonRequest += 1;
    const flowVersion = state.flowVersion;
    byId("status").textContent = "Making three directions…";
    state.selected = null;
    state.brief = null;
    state.script = "";
    state.draft = null;
    state.previous = null;
    state.baseline = null;
    state.backend = byId("backend").value;
    state.backendLabel = state.backend;
    byId("comparison").replaceChildren();
    byId("directions").classList.remove("empty-state");
    byId("directions").innerHTML = '<article class="generation-error" role="status"><strong>Generating 3 routes…</strong><p>Your brief stays available while we write.</p></article>';
    byId("edit-section").classList.add("hidden");
    byId("gremlin").classList.add("hidden");
    byId("arena").classList.add("hidden");
    byId("campaign").classList.add("hidden");
    try {
      const result = await api("generate", { brief: briefFromForm(), backend: state.backend });
      if (flowVersion !== state.flowVersion) return;
      state.brief = result.brief;
      state.submittedBrief = JSON.stringify(result.brief);
      state.backendLabel = result.backend;
      byId("backend-pill").textContent = result.backend;
      byId("directions").innerHTML = result.directions.map((direction, index) => `
        <article class="route-row"><div><span class="tag">${escapeHtml(direction.name)}</span><p class="route-angle">${escapeHtml(direction.concept)}</p></div>
          <h3>${escapeHtml(direction.hook)}</h3><button data-select="${index}" aria-pressed="false">View script</button></article>`).join("");
      document.querySelectorAll("[data-select]").forEach((button, index) => {
        button.onclick = () => chooseDirection(result.directions[index], button.closest(".route-row"));
      });
      byId("status").textContent = "Three directions are ready.";
      if (document.activeElement === button) {
        byId("directions-heading").focus();
      }
    } catch (error) {
      if (flowVersion !== state.flowVersion) return;
      byId("directions").innerHTML = `<article class="card"><span class="tag">Could not generate</span><p>${escapeHtml(error.message)}</p></article>`;
      byId("directions").innerHTML = `<article class="generation-error"><strong>Couldn’t make the routes.</strong><p>${escapeHtml(error.message)}</p><button id="try-again">Try again</button></article>`;
      byId("status").textContent = "Generation failed. Your brief is still here.";
      byId("try-again").onclick = () => byId("generate").click();
    } finally {
      button.disabled = false;
    }
  };

  byId("load-example").onclick = () => {
    const hasDraft = ["name", "description", "audience", "benefit"].some((id) => byId(id).value.trim());
    if (hasDraft && !window.confirm("Replace the current brief with the Northstar Coffee example?")) return;
    byId("name").value = "Northstar Coffee";
    byId("description").value = "A small-batch coffee subscription";
    byId("audience").value = "People working from home";
    byId("benefit").value = "Good coffee without another errand";
    byId("generate").focus();
  };

  for (const id of ["name", "description", "audience", "benefit", "tone", "duration", "platform", "cta", "required", "prohibited"]) {
    byId(id).addEventListener("input", updateBriefStatus);
    byId(id).addEventListener("change", updateBriefStatus);
  }

  function updateBriefStatus() {
    const label = byId("brief-edited");
    if (!state.submittedBrief) return;
    const changed = JSON.stringify(briefFromForm()) !== state.submittedBrief;
    label.classList.toggle("hidden", !changed);
    byId("settings-summary").textContent = `${byId("duration").value} seconds · ${byId("platform").value} · ${byId("tone").value}`;
  }

  byId("script").oninput = () => {
    state.scriptVersion += 1;
    if (state.draft === null) {
      state.script = byId("script").value;
      updateArenaScript();
    } else {
      state.draft = byId("script").value;
    }
    refreshChecks(visibleScript());
  };

  byId("rewrites").onclick = async (event) => {
    const action = event.target.dataset.action;
    if (!action || state.draft !== null) return;
    const buttons = [...document.querySelectorAll("#rewrites [data-action]")];
    const flowVersion = state.flowVersion;
    const request = ++state.scriptRequest;
    for (const button of buttons) button.disabled = true;
    byId("script").disabled = true;
    byId("undo").disabled = true;
    byId("status").textContent = "Preparing a rewrite draft…";
    try {
      const result = await api("rewrite", {
        brief: state.brief, text: state.script, action, backend: state.backend,
      });
      if (flowVersion !== state.flowVersion || request !== state.scriptRequest) return;
      showDraft(result.text, result.checks);
      byId("status").textContent = "Review the draft, then accept it or undo.";
    } catch (error) {
      if (flowVersion !== state.flowVersion || request !== state.scriptRequest) return;
      byId("script").disabled = false;
      byId("undo").disabled = false;
      for (const button of buttons) button.disabled = false;
      byId("status").textContent = error.message;
    }
  };

  byId("accept-rewrite").onclick = () => {
    if (state.draft === null) return;
    const accepted = state.draft;
    showAcceptedScript(accepted);
    byId("status").textContent = "Rewrite accepted.";
  };

  byId("undo").onclick = () => {
    if (state.draft !== null) {
      showAcceptedScript(state.script);
      byId("status").textContent = "Draft discarded.";
      return;
    }
    if (state.previous === null) return;
    const current = state.script;
    showAcceptedScript(state.previous);
    state.previous = current;
    byId("status").textContent = "Previous script restored.";
  };

  byId("challenge").onclick = async () => {
    const flowVersion = state.flowVersion;
    try {
      const result = await api("objection", { brief: state.brief, backend: state.backend });
      if (flowVersion !== state.flowVersion) return;
      byId("objection").textContent = result.objection;
      byId("objection-box").classList.remove("hidden");
    } catch (error) {
      if (flowVersion !== state.flowVersion) return;
      byId("gremlin-note").textContent = error.message;
    }
  };

  document.querySelectorAll("[data-gremlin]").forEach((button) => {
    button.onclick = () => {
      if (button.dataset.gremlin === "ignore") {
        byId("gremlin-note").textContent = "Challenge set aside.";
      } else if (button.dataset.gremlin === "incorporate") {
        showDraft(`${state.script}\n\nAUDIENCE QUESTION: ${byId("objection").textContent}`);
        byId("gremlin-note").textContent = "Review the draft, then accept it or undo.";
      } else {
        byId("verified").classList.remove("hidden");
        byId("apply-answer").classList.remove("hidden");
      }
    };
  });

  byId("apply-answer").onclick = () => {
    const verified = byId("verified").value.trim();
    if (!verified) {
      byId("gremlin-note").textContent = "Enter a verified detail before adding an answer.";
      return;
    }
    showDraft(`${state.script}\n\nRESPONSE: ${verified} ${state.brief.cta}`);
    byId("gremlin-note").textContent = "Review the draft, then accept it or undo.";
  };

  byId("arena").onclick = (event) => {
    const vote = event.target.dataset.vote;
    if (!vote) return;
    try {
      localStorage.setItem("ad-studio-vote", vote);
      byId("vote-note").textContent = "Vote kept in this browser only. A later vote replaces it.";
    } catch {
      byId("vote-note").textContent = "This browser did not allow saving the vote.";
    }
  };

  byId("pack").onclick = async () => {
    if (state.draft !== null) {
      byId("status").textContent = "Accept or undo the draft before building the pack.";
      return;
    }
    const flowVersion = state.flowVersion;
    const scriptVersion = state.scriptVersion;
    try {
      const result = await api("campaign", {
        brief: state.brief,
        direction: { ...state.selected, script: state.script },
        include_variants: byId("variants").checked,
      });
      if (flowVersion !== state.flowVersion || scriptVersion !== state.scriptVersion) return;
      byId("pack-text").innerHTML = renderCampaignPack(result);
      byId("pack-output").classList.remove("hidden");
    } catch (error) {
      if (flowVersion !== state.flowVersion) return;
      byId("status").textContent = error.message;
    }
  };

  function renderCampaignPack(pack) {
    const brief = pack.brief || {};
    const variants = (pack.variants || []).map((variant) => `
      <article class="deliverable-variant"><span class="tag">${escapeHtml(variant.label)}</span><p>${escapeHtml(variant.script)}</p></article>`).join("");
    const hooks = (pack.alternate_hooks || []).map((hook) => `<li>${escapeHtml(hook)}</li>`).join("");
    const ctas = (pack.alternate_ctas || []).map((cta) => `<li>${escapeHtml(cta)}</li>`).join("");
    return `<article class="campaign-sheet"><header><div><span class="tag">CAMPAIGN DRAFT</span><h3>${escapeHtml(brief.product_name || "Your campaign")}</h3></div><span class="tag">${escapeHtml(brief.platform || "Social video")} · ${escapeHtml(brief.duration || "")} sec</span></header>
      <section><span class="tag">HERO SCRIPT</span><p class="deliverable-copy">${escapeHtml(pack.main_script || "")}</p></section>
      ${variants ? `<section><span class="tag">CUTDOWNS</span>${variants}</section>` : ""}
      <div class="deliverable-lists"><section><span class="tag">ALTERNATE HOOKS</span><ul>${hooks}</ul></section><section><span class="tag">CALLS TO ACTION</span><ul>${ctas}</ul></section></div>
      <p class="deliverable-foot">Draft for review · Check all product claims before publishing.</p></article>`;
  }

  function download(name, content, type = "text/plain") {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  byId("download").onclick = () => download("campaign-pack.txt", byId("pack-text").textContent);

  byId("hear").onclick = async () => {
    const flowVersion = state.flowVersion;
    const scriptVersion = state.scriptVersion;
    try {
      const result = await api("speak", { text: state.script, voice: byId("voice").value });
      if (flowVersion !== state.flowVersion || scriptVersion !== state.scriptVersion) return;
      const audio = Uint8Array.from(result.audio.match(/.{1,2}/g), (byte) => parseInt(byte, 16));
      if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
      state.audioBlob = new Blob([audio], { type: "audio/wav" });
      state.audioUrl = URL.createObjectURL(state.audioBlob);
      const player = new Audio(state.audioUrl);
      await player.play();
      byId("audio-note").textContent = "Generated with the local system voice engine.";
    } catch (error) {
      if (flowVersion !== state.flowVersion) return;
      byId("audio-note").textContent = error.message;
    }
  };

  byId("download-audio").onclick = () => {
    if (!state.audioUrl) {
      byId("audio-note").textContent = "Generate a voice preview first.";
      return;
    }
    download("ad-preview.wav", state.audioBlob, "audio/wav");
  };

  window.addEventListener("pagehide", () => {
    if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  }, { once: true });

  api("voices", {}).then((result) => {
    for (const voice of result.voices) {
      const option = document.createElement("option");
      option.value = voice.id;
      option.textContent = voice.name;
      byId("voice").append(option);
    }
  }).catch((error) => { byId("audio-note").textContent = error.message; });
})();
