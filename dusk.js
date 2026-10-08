// Holzman "Dusk" page behaviour, shared by every page. Content never depends on this file:
// without it, everything is simply visible and still.
(function () {
  var root = document.documentElement;
  var reveals = [].slice.call(document.querySelectorAll('.reveal'));
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduce && 'IntersectionObserver' in window && reveals.length) {
    // Anything already on the first screen shows at once; only content below it animates in.
    var fold = window.innerHeight;
    reveals.forEach(function (el) { if (el.getBoundingClientRect().top < fold) el.classList.add('in'); });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(function (el) { if (!el.classList.contains('in')) io.observe(el); });
    root.classList.add('js');
  }
  // Seamless marquee: the track is copied until the copies cover the strip on any screen width
  // (each copy moves by its own width plus the gap). Copies are hidden from screen readers.
  [].forEach.call(document.querySelectorAll('[data-marquee]'), function (track) {
    var strip = track.parentNode, w = track.getBoundingClientRect().width || 1;
    var n = Math.max(1, Math.ceil(strip.getBoundingClientRect().width / w));
    for (var i = 0; i < n; i++) {
      var copy = track.cloneNode(true);
      copy.setAttribute('aria-hidden', 'true'); copy.removeAttribute('data-marquee');
      [].forEach.call(copy.querySelectorAll('a,button'), function (el) { el.setAttribute('tabindex', '-1'); });
      strip.appendChild(copy);
    }
  });
  // WCAG 2.2.2 (Pause, Stop, Hide): one switch in the footer pauses every looping animation.
  // The label names the action (no aria-pressed, which would contradict a changing label).
  // Hidden when the visitor's system already asks for reduced motion (nothing loops then).
  var toggle = document.querySelector('.motion-toggle');
  if (toggle && !reduce) {
    var still = false;
    try { still = localStorage.getItem('holzman-motion') === 'paused'; } catch (e) {}
    var apply = function () {
      root.classList.toggle('still', still);
      toggle.textContent = still ? 'Play animations' : 'Pause animations';
    };
    toggle.hidden = false; apply();
    toggle.addEventListener('click', function () {
      still = !still; apply();
      try { localStorage.setItem('holzman-motion', still ? 'paused' : 'playing'); } catch (e) {}
    });
  }
})();
