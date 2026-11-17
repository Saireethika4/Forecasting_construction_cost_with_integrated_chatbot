// Live page background: a blueprint truss that reacts to the pointer, above a site where a crane builds towers
(() => {
  const canvas = document.createElement('canvas');
  canvas.className = 'site-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.prepend(canvas);
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const CYAN = '88, 220, 236';
  const ORANGE = '255, 138, 31';
  const STEEL = '148, 170, 196';
  const FRAME_MS = 1000 / 30;
  const FLOOR_H = 13;
  const LINK_DIST = 150;
  const POINTER_DIST = 190;

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const saveData = navigator.connection && navigator.connection.saveData;
  const still = () => motion.matches || saveData;

  let width = 0;
  let height = 0;
  let ground = 0;
  let nodes = [];
  let towers = [];
  let sparks = [];
  let crane = null;
  let frameId = null;
  let lastFrame = 0;
  const pointer = { x: -9999, y: -9999, active: false };

  const random = (low, high) => low + Math.random() * (high - low);

  function buildScene() {
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ground = height - 6;

    const count = Math.min(70, Math.max(22, Math.round((width * height) / 26000)));
    nodes = Array.from({ length: count }, () => ({
      x: random(0, width),
      y: random(0, height * 0.82),
      vx: random(-0.22, 0.22),
      vy: random(-0.16, 0.16),
    }));

    const maxFloors = Math.max(6, Math.floor((height * 0.3) / FLOOR_H));
    const craneX = width < 700 ? width * 0.16 : width * 0.56;
    const reach = width < 700 ? width * 0.72 : Math.min(width * 0.36, 520);
    towers = [];
    for (let x = random(-20, 10); x < width; ) {
      const towerWidth = random(46, 92);
      const center = x + towerWidth / 2;
      const target = Math.round(random(maxFloors * 0.35, maxFloors));
      const buildable = center > craneX + 46 && center < craneX + reach - 10;
      towers.push({
        x,
        width: towerWidth,
        center,
        target,
        buildable,
        floors: buildable ? Math.round(random(1, target)) : target,
        lights: Array.from({ length: 96 }, () => Math.random()),
      });
      x += towerWidth + random(8, 30);
    }
    if (still()) towers.forEach((tower) => { tower.floors = tower.target; });

    crane = {
      x: craneX,
      top: ground - maxFloors * FLOOR_H - 62,
      reach,
      trolley: craneX + reach / 2,
      cable: 26,
      phase: 'travel',
      target: null,
      wait: 0,
    };
  }

  function chooseTarget() {
    let open = towers.filter((tower) => tower.buildable && tower.floors < tower.target);
    if (!open.length) {
      // The block is finished, so clear it and start the next phase of work
      towers.forEach((tower) => { if (tower.buildable) tower.floors = 1; });
      open = towers.filter((tower) => tower.buildable);
    }
    return open.length ? open[Math.floor(Math.random() * open.length)] : null;
  }

  function stepCrane() {
    const jibY = crane.top + 22;
    if (crane.wait > 0) {
      crane.wait -= 1;
      return;
    }
    if (crane.phase === 'travel') {
      if (!crane.target) crane.target = chooseTarget();
      if (!crane.target) return;
      const distance = crane.target.center - crane.trolley;
      crane.trolley += Math.sign(distance) * Math.min(Math.abs(distance), 1.8);
      if (Math.abs(distance) < 1) crane.phase = 'lower';
    } else if (crane.phase === 'lower') {
      const roof = ground - crane.target.floors * FLOOR_H - FLOOR_H - jibY;
      crane.cable = Math.min(crane.cable + 2.2, roof);
      if (crane.cable >= roof) {
        crane.target.floors += 1;
        const y = ground - crane.target.floors * FLOOR_H;
        for (let i = 0; i < 12; i += 1) {
          sparks.push({ x: crane.target.center + random(-14, 14), y, vx: random(-1.4, 1.4), vy: random(-2.2, -0.3), life: 1 });
        }
        crane.phase = 'raise';
        crane.wait = 10;
      }
    } else {
      crane.cable = Math.max(crane.cable - 2.8, 26);
      if (crane.cable <= 26) {
        crane.phase = 'travel';
        crane.target = null;
        crane.wait = 16;
      }
    }
  }

  function line(x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function drawTruss() {
    ctx.lineWidth = 1;
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const distance = Math.hypot(a.x - b.x, a.y - b.y);
        if (distance < LINK_DIST) {
          ctx.strokeStyle = `rgba(${STEEL}, ${0.3 * (1 - distance / LINK_DIST)})`;
          line(a.x, a.y, b.x, b.y);
        }
      }
      if (pointer.active) {
        const distance = Math.hypot(a.x - pointer.x, a.y - pointer.y);
        if (distance < POINTER_DIST) {
          ctx.strokeStyle = `rgba(${ORANGE}, ${0.42 * (1 - distance / POINTER_DIST)})`;
          line(a.x, a.y, pointer.x, pointer.y);
        }
      }
      ctx.fillStyle = `rgba(${CYAN}, 0.55)`;
      ctx.fillRect(a.x - 1.5, a.y - 1.5, 3, 3);
    }
  }

  function drawTowers(time) {
    towers.forEach((tower) => {
      const top = ground - tower.floors * FLOOR_H;
      const towerHeight = tower.floors * FLOOR_H;
      ctx.fillStyle = 'rgba(12, 18, 26, 0.72)';
      ctx.fillRect(tower.x, top, tower.width, towerHeight);
      ctx.strokeStyle = `rgba(${CYAN}, ${tower.buildable ? 0.34 : 0.16})`;
      ctx.lineWidth = 1;
      ctx.strokeRect(tower.x + 0.5, top + 0.5, tower.width - 1, towerHeight);

      const columns = Math.max(2, Math.floor(tower.width / 16));
      const gap = tower.width / columns;
      for (let floor = 0; floor < tower.floors; floor += 1) {
        for (let column = 0; column < columns; column += 1) {
          const seed = tower.lights[(floor * 7 + column * 3) % tower.lights.length];
          if (seed < 0.62) continue;
          const glow = 0.1 + 0.2 * Math.abs(Math.sin(time / 2600 + seed * 40));
          ctx.fillStyle = seed > 0.9 ? `rgba(${ORANGE}, ${glow + 0.1})` : `rgba(${CYAN}, ${glow})`;
          ctx.fillRect(tower.x + column * gap + gap * 0.3, ground - (floor + 1) * FLOOR_H + 4, gap * 0.4, 5);
        }
      }
    });
    ctx.strokeStyle = `rgba(${STEEL}, 0.3)`;
    line(0, ground + 0.5, width, ground + 0.5);
  }

  function drawCrane() {
    const { x, top, reach, trolley, cable } = crane;
    const jibY = top + 22;
    const mast = 9;
    ctx.strokeStyle = `rgba(${ORANGE}, 0.5)`;
    ctx.lineWidth = 1;
    line(x - mast, ground, x - mast, jibY);
    line(x + mast, ground, x + mast, jibY);
    for (let y = ground, flip = false; y > jibY; y -= 18, flip = !flip) {
      line(flip ? x - mast : x + mast, y, flip ? x + mast : x - mast, y - 18);
    }
    // Jib, counter-jib, apex and tie lines
    line(x - reach * 0.22, jibY, x + reach, jibY);
    line(x - reach * 0.22, jibY + 7, x + reach * 0.9, jibY + 7);
    line(x, top, x + reach * 0.7, jibY);
    line(x, top, x - reach * 0.22, jibY);
    line(x - mast, jibY, x, top);
    line(x + mast, jibY, x, top);
    for (let along = x + 16, flip = false; along < x + reach * 0.9; along += 16, flip = !flip) {
      line(along, flip ? jibY : jibY + 7, along + 16, flip ? jibY + 7 : jibY);
    }
    ctx.fillStyle = `rgba(${ORANGE}, 0.55)`;
    ctx.fillRect(x - reach * 0.22 - 2, jibY + 1, 20, 12);

    ctx.strokeStyle = `rgba(${CYAN}, 0.6)`;
    ctx.fillStyle = `rgba(${ORANGE}, 0.9)`;
    ctx.fillRect(trolley - 6, jibY + 5, 12, 5);
    line(trolley, jibY + 9, trolley, jibY + cable);
    if (crane.phase !== 'raise') {
      ctx.fillStyle = `rgba(${ORANGE}, 0.7)`;
      ctx.fillRect(trolley - 19, jibY + cable, 38, 8);
    }
  }

  function drawSparks() {
    sparks = sparks.filter((spark) => spark.life > 0);
    sparks.forEach((spark) => {
      spark.x += spark.vx;
      spark.y += spark.vy;
      spark.vy += 0.09;
      spark.life -= 0.035;
      ctx.fillStyle = `rgba(${ORANGE}, ${spark.life})`;
      ctx.fillRect(spark.x, spark.y, 2, 2);
    });
  }

  function stepNodes() {
    nodes.forEach((node) => {
      node.x += node.vx;
      node.y += node.vy;
      if (node.x < 0 || node.x > width) node.vx *= -1;
      if (node.y < 0 || node.y > height * 0.82) node.vy *= -1;
    });
  }

  function draw(time) {
    ctx.clearRect(0, 0, width, height);
    drawTruss();
    drawTowers(time);
    drawCrane();
    drawSparks();
  }

  function loop(time) {
    frameId = requestAnimationFrame(loop);
    if (time - lastFrame < FRAME_MS) return;
    lastFrame = time;
    stepNodes();
    stepCrane();
    draw(time);
  }

  function start() {
    if (frameId !== null) cancelAnimationFrame(frameId);
    frameId = null;
    if (still()) {
      draw(0);
    } else if (!document.hidden) {
      frameId = requestAnimationFrame(loop);
    }
  }

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { buildScene(); start(); }, 150);
  });
  document.addEventListener('visibilitychange', start);
  motion.addEventListener('change', () => { buildScene(); start(); });
  window.addEventListener('pointermove', (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.active = event.pointerType === 'mouse';
  }, { passive: true });
  document.addEventListener('mouseleave', () => { pointer.active = false; });

  buildScene();
  start();
})();
