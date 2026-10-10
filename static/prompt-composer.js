/**
 * Shared agent-style prompt box: auto-resize textarea + voice/send toggle.
 */
function resizeAgentTextarea(textarea) {
  if (!textarea) {
    return;
  }
  const box = textarea.closest(".agent-prompt-box");
  const style = window.getComputedStyle(textarea);
  const lineHeight = parseFloat(style.lineHeight) || 22;
  const maxHeight = parseFloat(style.maxHeight) || 112;

  textarea.style.height = "0";
  const contentHeight = textarea.scrollHeight;
  const nextHeight = Math.min(contentHeight, maxHeight);
  textarea.style.height = `${nextHeight}px`;

  const isMultiline = contentHeight > lineHeight + 6;
  box?.classList.toggle("is-multiline", isMultiline);
  textarea.style.overflowY = isMultiline && contentHeight > maxHeight ? "auto" : "hidden";
}

/**
 * @param {{
 *   form: HTMLFormElement,
 *   textarea: HTMLTextAreaElement,
 *   sendBtn: HTMLButtonElement,
 *   showSend?: () => boolean,
 *   isRunning?: () => boolean,
 *   onVoiceUnavailable?: (message: string) => void,
 * }} options
 */
function initPromptComposerVoice(options) {
  const { form, textarea, sendBtn } = options;
  const showSend = options.showSend || (() => Boolean(textarea.value.trim()));
  const isRunning = options.isRunning || (() => false);
  const notify =
    options.onVoiceUnavailable ||
    function (message) {
      if (typeof openAppAlert === "function") {
        void openAppAlert({ title: "Voice input", message });
      } else {
        window.alert(message);
      }
    };

  const SpeechRecognitionCtor =
    typeof window !== "undefined"
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;

  let voiceRecognition = null;
  let voiceListening = false;
  let voiceInputPrefix = "";

  const stopVoiceInput = () => {
    voiceListening = false;
    sendBtn.classList.remove("is-listening");
    try {
      voiceRecognition?.stop();
    } catch {
      /* ignore */
    }
  };

  const syncComposerActionButton = () => {
    const running = isRunning();
    sendBtn.classList.toggle("is-stop", running);
    if (running) {
      sendBtn.classList.remove("is-send-mode", "is-voice-mode");
      sendBtn.type = "button";
      sendBtn.setAttribute("aria-label", "Stop");
      return;
    }
    const send = showSend();
    sendBtn.classList.toggle("is-send-mode", send);
    sendBtn.classList.toggle("is-voice-mode", !send);
    sendBtn.type = send ? "submit" : "button";
    sendBtn.setAttribute(
      "aria-label",
      send ? "Send message" : SpeechRecognitionCtor ? "Voice input" : "Voice input unavailable",
    );
  };

  const startVoiceInput = () => {
    if (!SpeechRecognitionCtor) {
      notify("Your browser does not support speech recognition. Type your message instead.");
      return;
    }
    if (voiceListening) {
      stopVoiceInput();
      return;
    }
    if (isRunning()) {
      return;
    }
    stopVoiceInput();
    voiceRecognition = new SpeechRecognitionCtor();
    voiceRecognition.continuous = false;
    voiceRecognition.interimResults = true;
    voiceRecognition.lang = document.documentElement.lang || "en-US";

    voiceRecognition.onstart = () => {
      voiceInputPrefix = textarea.value.trim();
      voiceListening = true;
      sendBtn.classList.add("is-listening");
    };
    voiceRecognition.onend = () => {
      voiceListening = false;
      sendBtn.classList.remove("is-listening");
    };
    voiceRecognition.onerror = (event) => {
      voiceListening = false;
      sendBtn.classList.remove("is-listening");
      if (event.error === "not-allowed") {
        notify("Allow microphone access for this site in your browser settings, then try again.");
      } else if (event.error !== "aborted" && event.error !== "no-speech") {
        notify("Could not capture speech. Try again or type your message.");
      }
    };
    voiceRecognition.onresult = (event) => {
      let committed = "";
      let interim = "";
      for (let i = 0; i < event.results.length; i += 1) {
        const part = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) {
          committed += part;
        } else {
          interim = part;
        }
      }
      const pieces = [];
      if (voiceInputPrefix) {
        pieces.push(voiceInputPrefix);
      }
      if (committed.trim()) {
        pieces.push(committed.trim());
      }
      if (interim.trim()) {
        pieces.push(interim.trim());
      }
      textarea.value = pieces.join(" ").trim();
      resizeAgentTextarea(textarea);
      syncComposerActionButton();
    };

    try {
      voiceRecognition.start();
    } catch {
      notify("Could not start voice input. Try again or type your message.");
    }
  };

  sendBtn.addEventListener("click", (event) => {
    if (isRunning()) {
      return;
    }
    if (sendBtn.classList.contains("is-voice-mode")) {
      event.preventDefault();
      event.stopPropagation();
      startVoiceInput();
    }
  });

  textarea.addEventListener("input", () => {
    resizeAgentTextarea(textarea);
    syncComposerActionButton();
  });

  syncComposerActionButton();
  resizeAgentTextarea(textarea);

  return { syncComposerActionButton, stopVoiceInput };
}
