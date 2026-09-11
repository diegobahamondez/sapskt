/* Shows split and photo lightbox modal functionality */
(function () {
  var upSec = document.getElementById('upcoming');
  if (upSec) {
    var upList = upSec.querySelector('.pk-shows');
    var pastSec = document.getElementById('shows');
    var pastList = pastSec ? pastSec.querySelector('.pk-shows') : null;

    if (upList) {
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
    }
  }

  /* Section numbers renumbering */
  var n = 0;
  Array.prototype.forEach.call(
    document.querySelectorAll('.pk-section, .site-section'), function (sec) {
      if (sec.hidden) return;
      var num = sec.querySelector('.pk-num, .section-num');
      if (!num) return;
      n += 1;
      num.textContent = n < 10 ? '0' + n : String(n);
    });

  /* Photo Lightbox Modal */
  (function () {
    var photos = Array.prototype.slice.call(document.querySelectorAll('.pk-photo a'));
    var modal = document.getElementById('photo-modal');
    if (!photos.length || !modal) return;

    var modalImg = document.getElementById('pk-modal-img');
    var modalCaption = document.getElementById('pk-modal-caption');
    var modalCredit = document.getElementById('pk-modal-credit');
    var modalDownload = document.getElementById('pk-modal-download');
    var closeBtn = modal.querySelector('.pk-modal-close');
    var prevBtn = modal.querySelector('.pk-modal-nav--prev');
    var nextBtn = modal.querySelector('.pk-modal-nav--next');
    var currentIndex = 0;

    var igIcon = '<svg class="ig-icon" viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="2" y="2" width="20" height="20" rx="5.5"/><circle cx="12" cy="12" r="4.4"/><circle cx="17.6" cy="6.4" r="1.1" fill="currentColor" stroke="none"/></svg>';

    function showPhoto(index) {
      if (index < 0) index = photos.length - 1;
      if (index >= photos.length) index = 0;
      currentIndex = index;

      var a = photos[currentIndex];
      var href = a.getAttribute('href');
      var caption = a.getAttribute('data-caption') || '';
      var credit = a.getAttribute('data-credit') || '';
      var handle = a.getAttribute('data-handle') || '';

      modalImg.src = href;
      modalImg.alt = caption;
      modalCaption.textContent = caption;

      if (credit) {
        var creditHtml = 'Photo by ' + credit;
        if (handle) {
          creditHtml += ' (<a class="pk-credit" href="https://instagram.com/' + handle + '" target="_blank" rel="noopener">' + igIcon + '@' + handle + '</a>)';
        }
        modalCredit.innerHTML = creditHtml;
        modalCredit.style.display = '';
      } else {
        modalCredit.style.display = 'none';
      }

      modalDownload.setAttribute('href', href);

      if (typeof modal.showModal === 'function') {
        if (!modal.open) modal.showModal();
      } else {
        modal.setAttribute('open', '');
      }
      document.body.style.overflow = 'hidden';
    }

    function closeModal() {
      if (typeof modal.close === 'function') {
        modal.close();
      } else {
        modal.removeAttribute('open');
      }
      document.body.style.overflow = '';
    }

    photos.forEach(function (a, i) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        showPhoto(i);
      });
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    if (prevBtn) prevBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      showPhoto(currentIndex - 1);
    });
    if (nextBtn) nextBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      showPhoto(currentIndex + 1);
    });

    document.addEventListener('keydown', function (e) {
      var isOpen = modal.open || modal.hasAttribute('open');
      if (!isOpen) return;
      if (e.key === 'Escape') closeModal();
      else if (e.key === 'ArrowLeft') showPhoto(currentIndex - 1);
      else if (e.key === 'ArrowRight') showPhoto(currentIndex + 1);
    });
  })();
})();
