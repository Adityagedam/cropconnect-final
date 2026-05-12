import { Mic, MicOff, Send } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { languages } from "../LanguageSelect";

const renderChatText = (value) =>
  String(value ?? "")
    .split("\n")
    .map((line, lineIndex, lines) => (
      <span key={`line-${lineIndex}`}>
        {line.split(/(\*\*.*?\*\*)/g).map((part, partIndex) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={`part-${lineIndex}-${partIndex}`}>{part.slice(2, -2)}</strong>
          ) : (
            <span key={`part-${lineIndex}-${partIndex}`}>{part}</span>
          )
        )}
        {lineIndex < lines.length - 1 && <br />}
      </span>
    ));

export default function AiChatPanel({
  colors,
  chatContainerRef,
  chatMessages,
  userName,
  isTyping,
  showSuggestions,
  suggestionChips,
  ct,
  handleSuggestionClick,
  chatInput,
  setChatInput,
  handleSendMessage,
  isListening,
  startListening,
  stopListening,
  language,
}) {
  return (
    <div className="space-y-6">
      <div className="p-5 rounded-xl bg-white border border-[#e8e3d8] shadow-sm">
        <div className="rounded-xl overflow-hidden flex flex-col" style={{ height: "500px" }}>
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`flex gap-3 ${msg.type === "user" ? "flex-row-reverse" : ""}`}>
                <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={msg.type === "bot" ? { background: colors.greenDark, color: "white" } : { background: `linear-gradient(135deg, ${colors.greenMid}, ${colors.terracotta})`, color: "white" }}>
                  {msg.type === "bot" ? "AI" : (userName.charAt(0) || "U")}
                </div>
                <div className={`max-w-[85%] sm:max-w-[70%] p-4 rounded-xl ${msg.type === "bot" ? "bg-white border border-[#e8e3d8]" : ""}`} style={msg.type === "bot" ? { borderTopLeftRadius: "4px" } : { background: colors.greenDark, borderTopRightRadius: "4px" }}>
                  <p data-no-translate="true" className="text-sm" style={{ color: msg.type === "bot" ? colors.textDark : colors.cream }}>{renderChatText(msg.text)}</p>
                  {msg.type === "user" && (
                    <p className="mt-2 text-xs" style={{ color: colors.goldLight }}>
                      Farm assistant
                    </p>
                  )}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: colors.greenDark, color: "white" }}>AI</div>
                <div className="p-4 rounded-xl bg-white border border-[#e8e3d8]">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
          </div>

          {showSuggestions && (
            <div className="px-4 py-2 flex gap-2 flex-wrap border-t" style={{ borderColor: colors.creamDark }}>
              {suggestionChips.map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleSuggestionClick(ct(chip), chip)}
                  className="px-3 py-1.5 text-sm rounded-full border transition-colors hover:bg-gray-50"
                  style={{ borderColor: colors.creamDark, color: colors.textMid }}
                >
                  {ct(chip)}
                </button>
              ))}
            </div>
          )}

          <div className="flex flex-col gap-2 p-4 border-t" style={{ borderColor: colors.creamDark }}>
            <div className="flex gap-2">
              <Input value={chatInput} onChange={(event) => setChatInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && handleSendMessage()} placeholder={ct("chatPlaceholder")} className="flex-1" />
              <Button
                onClick={isListening ? stopListening : startListening}
                disabled={isTyping}
                className={`px-3 ${isListening ? "bg-red-500 hover:bg-red-600" : "bg-blue-500 hover:bg-blue-600"}`}
              >
                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </Button>
              <Button onClick={() => handleSendMessage()} disabled={!chatInput.trim() || isTyping} className="bg-green-600 hover:bg-green-700">
                <Send className="w-4 h-4" />
              </Button>
            </div>
            {language !== "en" && (
              <p className="text-xs text-gray-500">
                Voice input listens in {languages.find((lang) => lang.code === language)?.name || language}; replies use the selected language.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
