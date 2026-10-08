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
  // Seamless marquee: the track is duplicated once; the copy is hidden from screen readers.
  [].forEach.call(document.querySelectorAll('[data-marquee]'), function (track) {
    var copy = track.cloneNode(true);
    copy.setAttribute('aria-hidden', 'true'); copy.removeAttribute('data-marquee');
    [].forEach.call(copy.querySelectorAll('a,button'), function (n) { n.setAttribute('tabindex', '-1'); });
    track.parentNode.appendChild(copy);
  });
})();
