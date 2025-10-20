/* /assets/slideshow.js — drop-in with debug instrumentation */

const UKPA_SLIDESHOW_DEBUG = true;
function report(msg, extra) {
  console.error('[slideshow]', msg, extra || '');
  if (UKPA_SLIDESHOW_DEBUG) alert(`[slideshow] ${msg}`);
}

function parseSlidesFromData(wrap) {
  // Preferred simple form: data-files="file1.svg,file2.svg" (+ optional data-base="/images/slides/")
  const csv = wrap.getAttribute('data-files');
  if (csv !== null) {
    const base = (wrap.getAttribute('data-base') || '').replace(/\/?$/, '/');
    const files = csv.split(',').map(s => s.trim()).filter(Boolean);
    if (!files.length) {
      report('data-files is present but empty');
      return [];
    }
    return files.map((name, idx) => ({
      src: base && !name.startsWith('/') ? base + name : name,
      alt: wrap.getAttribute('data-alt') || `Slide ${idx + 1}`,
    }));
  }

  // Back-compat JSON form: data-slides='[{"src":"/path.svg","alt":"..."}]'
  const json = wrap.getAttribute('data-slides');
  if (json !== null) {
    try {
      const arr = JSON.parse(json);
      if (!Array.isArray(arr) || !arr.length) {
        report('data-slides parsed but is empty or not an array');
        return [];
      }
      // Ensure minimal shape
      return arr.filter(s => s && s.src).map((s, i) => ({
        src: s.src,
        alt: s.alt || `Slide ${i + 1}`,
      }));
    } catch (e) {
      report('Invalid JSON in data-slides (see console for details)');
      console.error('data-slides value:', json);
      console.error(e);
      return [];
    }
  }

  report('No data-files or data-slides attribute found on slideshow wrapper', wrap);
  return [];
}

function initSlideshow(wrap) {
  const slides = parseSlidesFromData(wrap);
  if (!slides.length) {
    report('No slides available for this slideshow instance.');
    return;
  }

  const img  = wrap.querySelector('.ukpa-slide-img');
  const next = wrap.querySelector('.ukpa-slide-next');
  const cEl  = wrap.querySelector('.ukpa-slide-count');
  const tEl  = wrap.querySelector('.ukpa-slide-total');

  if (!img) {
    report('Missing .ukpa-slide-img inside slideshow wrapper');
    return;
  }
  if (tEl) tEl.textContent = String(slides.length);

  let i = 0;

  function show(idx) {
    const s = slides[idx];
    if (!s) return;
    img.src = s.src;
    img.alt = s.alt || `Slide ${idx + 1}`;
    if (cEl) cEl.textContent = String(idx + 1);
    if (UKPA_SLIDESHOW_DEBUG && idx === 0) {
      console.log('[slideshow] showing first slide:', s);
    }
  }

  // Report image load failures (path/case/CORS/etc.)
  img.addEventListener('error', () => {
    report('Image failed to load: ' + img.src);
  });

  show(i);

  const advance = () => { i = (i + 1) % slides.length; show(i); };
  const back    = () => { i = (i - 1 + slides.length) % slides.length; show(i); };

  next?.addEventListener('click', advance);

  // Keyboard navigation
  wrap.tabIndex = 0;
  wrap.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'Enter') {
      e.preventDefault(); advance();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault(); back();
    }
  });

  // Basic swipe navigation
  let sx = 0, sy = 0;
  wrap.addEventListener('touchstart', (e) => {
    const t = e.changedTouches[0]; sx = t.clientX; sy = t.clientY;
  }, { passive: true });

  wrap.addEventListener('touchend', (e) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dx) > 30 && Math.abs(dx) > Math.abs(dy)) {
      dx < 0 ? advance() : back();
    } else {
      // treat tap as next
      advance();
    }
  }, { passive: true });

  // Preload remaining slides
  slides.slice(1).forEach(s => { const pre = new Image(); pre.src = s.src; });
}

function initAll() {
  const wraps = document.querySelectorAll('.ukpa-slideshow');
  if (!wraps.length) {
    report('No .ukpa-slideshow elements found on this page');
    return;
  }
  wraps.forEach(initSlideshow);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAll);
} else {
  initAll();
}

