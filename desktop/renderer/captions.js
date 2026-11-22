// Turns pipeline events into the text the overlay shows. No DOM here, so it is unit-tested.
export class CaptionView {
  constructor() { this.seq = -1; this.latestSeq = -1; this.current = null; }
  reset() { this.seq = -1; this.latestSeq = -1; this.current = null; }

  // Returns the caption to show, or null when the event should not change the screen.
  accept(event, { displayMode = 'both', finalOnly = false } = {}) {
    if (event.type === 'partial') {
      if (finalOnly || event.seq <= this.seq || event.seq < this.latestSeq) return null;
      // A partial without its translation would replace a finished line with half a line.
      if (displayMode !== 'original' && !event.translation && this.current?.translation) return null;
      this.latestSeq = event.seq;
      return this.show(event, false, displayMode);
    }
    if (event.type === 'final') {
      if (event.seq <= this.seq || event.seq < this.latestSeq) return null;
      if (!event.original && !event.translation) return null;
      this.seq = this.latestSeq = event.seq;
      return this.show(event, true, displayMode);
    }
    return null;
  }

  show(event, final, displayMode) {
    const original = String(event.original || '').trim(), translation = String(event.translation || '').trim();
    const caption = { final, original: '', translation: '', note: '' };
    if (displayMode === 'original') caption.original = original;
    else if (displayMode === 'zh') {
      caption.translation = translation;
      if (!translation && event.translation_unavailable) { caption.original = original; caption.note = '翻譯暫時不可用，先顯示原文'; }
    } else { caption.original = original; caption.translation = translation; }
    if (!caption.original && !caption.translation) return null;
    this.current = caption;
    return caption;
  }
}

// How long a caption stays when nothing new arrives: longer lines stay longer (2.5–8 s).
export function holdMs(caption) {
  const text = caption ? caption.translation || caption.original : '';
  return Math.min(8000, Math.max(2500, 1500 + Array.from(text).length * 120));
}
