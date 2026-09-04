/* Shows are split into upcoming and past at build time, which is correct on
   the day of the deploy. This re-checks in the browser so every page stays
   right on later visits without a rebuild. Progressive enhancement: with the
   script blocked, the build-time split still stands. */
(function () {
  var upSec = document.getElementById('upcoming');
  if (!upSec) return;
  var upList = upSec.querySelector('.pk-shows');
  if (!upList) return;
  var pastSec = document.getElementById('shows');
  var pastList = pastSec ? pastSec.querySelector('.pk-shows') : null;

  var today = new Date();
  today.setHours(0, 0, 0, 0);

  var stale = [];
  Array.prototype.forEach.call(upList.children, function (li) {
    var iso = li.getAttribute('data-date');
    if (!iso) return;
    var p = iso.split('-');
    if (new Date(+p[0], +p[1] - 1, +p[2]) < today) stale.push(li);
  });

  if (stale.length && pastList) {
    stale.forEach(function (li) { pastList.appendChild(li); });
    var items = Array.prototype.slice.call(pastList.children);
    items.sort(function (a, b) {
      var da = a.getAttribute('data-date'), db = b.getAttribute('data-date');
      if (!da && !db) return 0;
      if (!da) return 1;
      if (!db) return -1;
      return db.localeCompare(da);
    });
    items.forEach(function (li) { pastList.appendChild(li); });
  }

  if (!upList.children.length) upSec.hidden = true;

  /* Section numbers are baked in at build time, so renumber whatever is still
     visible rather than leaving a gap. Both page types are covered: the press
     kit uses .pk-section/.pk-num, the homepage .site-section/.section-num. */
  var n = 0;
  Array.prototype.forEach.call(
    document.querySelectorAll('.pk-section, .site-section'), function (sec) {
      if (sec.hidden) return;
      var num = sec.querySelector('.pk-num, .section-num');
      if (!num) return;
      n += 1;
      num.textContent = n < 10 ? '0' + n : String(n);
    });
})();
