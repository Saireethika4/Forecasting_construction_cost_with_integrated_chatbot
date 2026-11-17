// Menu toggles and scroll reveals shared by every page
document.querySelectorAll('[data-toggle]').forEach((button) => {
  const target = document.getElementById(button.dataset.toggle);
  const scrim = document.getElementById('scrim');
  const setOpen = (open) => {
    target.classList.toggle('is-open', open);
    if (scrim) scrim.classList.toggle('is-open', open);
    button.setAttribute('aria-expanded', String(open));
  };
  button.addEventListener('click', () => setOpen(!target.classList.contains('is-open')));
  if (scrim) scrim.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && target.classList.contains('is-open')) {
      setOpen(false);
      button.focus();
    }
  });
});

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

document.querySelectorAll('.panel:not(.result-card):not(.chat), .page-head').forEach((element) => {
  element.classList.add('reveal');
});

// Count up to the number already on the page, which stays there if scripts or motion are off
function countUp(element) {
  const match = element.textContent.match(/\d[\d,]*(\.\d+)?/);
  if (!match || calm) return;
  const target = Number(match[0].replace(/,/g, ''));
  const decimals = match[1] ? match[1].length - 1 : 0;
  const locale = ['en-US', 'en-IN'].find((name) => (
    target.toLocaleString(name, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) === match[0]
  ));
  if (!locale || target === 0) return;
  const original = element.textContent;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min((now - startedAt) / 1000, 1);
    if (progress === 1) {
      element.textContent = original;
      return;
    }
    const value = target * (1 - (1 - progress) ** 3);
    element.textContent = original.replace(match[0], value.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

const revealed = document.querySelectorAll('.reveal');
const counters = document.querySelectorAll('.stat strong, .stat-big, .result-amount');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    let stagger = 0;
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const element = entry.target;
      observer.unobserve(element);
      if (element.matches('.reveal')) {
        element.style.transitionDelay = `${stagger}ms`;
        stagger = Math.min(stagger + 70, 280);
        element.classList.add('is-in');
        // Hand transforms back to the element's own hover styles once it has landed
        setTimeout(() => {
          element.classList.remove('reveal', 'is-in');
          element.style.transitionDelay = '';
        }, 1000);
      } else {
        countUp(element);
      }
    });
  }, { threshold: 0, rootMargin: '0px 0px -5% 0px' });
  revealed.forEach((element) => observer.observe(element));
  counters.forEach((element) => observer.observe(element));
} else {
  revealed.forEach((element) => element.classList.add('is-in'));
}

if (finePointer && !calm) {
  // A light that follows the pointer across panels
  document.querySelectorAll('.panel').forEach((panel) => {
    panel.addEventListener('pointermove', (event) => {
      const box = panel.getBoundingClientRect();
      panel.style.setProperty('--mx', `${event.clientX - box.left}px`);
      panel.style.setProperty('--my', `${event.clientY - box.top}px`);
    }, { passive: true });
  });
  document.querySelectorAll('.tile, .feature').forEach((card) => {
    card.addEventListener('pointermove', (event) => {
      const box = card.getBoundingClientRect();
      const x = (event.clientX - box.left) / box.width - 0.5;
      const y = (event.clientY - box.top) / box.height - 0.5;
      card.style.transform = `perspective(800px) rotateX(${-y * 5}deg) rotateY(${x * 5}deg) translateY(-3px)`;
    }, { passive: true });
    card.addEventListener('pointerleave', () => { card.style.transform = ''; });
  });
}

// Show that a submitted form is working, since training and estimates can take a moment
document.querySelectorAll('form').forEach((form) => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('.train-btn, .submit-btn');
    if (button) button.classList.add('is-busy');
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('.is-busy').forEach((button) => button.classList.remove('is-busy'));
});
