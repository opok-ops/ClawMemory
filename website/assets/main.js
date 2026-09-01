/* ========== MindForge v5.5.8 - Liquid Glass UI ========== */

// Particle Background Animation
(function() {
  const canvas = document.getElementById('particleCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height;
  let particles = [];
  let mouseX = 0;
  let mouseY = 0;
  let mouseActive = false;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() { this.reset(); }

    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.3;
      this.vy = (Math.random() - 0.5) * 0.3;
      this.size = Math.random() * 2 + 0.5;
      this.color = Math.random() > 0.5 ? '#00d4ff' : '#a855f7';
      this.alpha = Math.random() * 0.4 + 0.1;
      this.pulseSpeed = Math.random() * 0.02 + 0.01;
      this.pulsePhase = Math.random() * Math.PI * 2;
    }

    update(time) {
      this.x += this.vx;
      this.y += this.vy;

      if (mouseActive) {
        const dx = mouseX - this.x;
        const dy = mouseY - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          const force = (150 - dist) / 150;
          this.vx += dx * force * 0.001;
          this.vy += dy * force * 0.001;
        }
      }

      this.vx *= 0.99;
      this.vy *= 0.99;

      if (this.x < 0) this.x = width;
      if (this.x > width) this.x = 0;
      if (this.y < 0) this.y = height;
      if (this.y > height) this.y = 0;

      this.alpha = 0.1 + Math.sin(time * this.pulseSpeed + this.pulsePhase) * 0.15;
    }

    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = this.color;
      ctx.globalAlpha = this.alpha;
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  function initParticles() {
    particles = [];
    const particleCount = Math.min(120, Math.floor(width * height / 15000));
    for (let i = 0; i < particleCount; i++) {
      particles.push(new Particle());
    }
  }

  function drawConnections() {
    const maxDist = 120;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < maxDist) {
          const alpha = (1 - dist / maxDist) * 0.15;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
  }

  let animationTime = 0;
  function animate() {
    animationTime += 1;
    ctx.clearRect(0, 0, width, height);
    particles.forEach(p => { p.update(animationTime); p.draw(); });
    drawConnections();
    requestAnimationFrame(animate);
  }

  document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    mouseActive = true;
  });
  document.addEventListener('mouseleave', () => { mouseActive = false; });

  resize();
  initParticles();
  animate();

  window.addEventListener('resize', () => { resize(); initParticles(); });
})();

// Copy button functionality
document.querySelector('.copy-btn')?.addEventListener('click', function() {
  const code = document.querySelector('.code-block code');
  if (code) {
    navigator.clipboard.writeText(code.textContent).then(() => {
      const originalHTML = this.innerHTML;
      this.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
      this.style.color = '#10b981';
      this.style.borderColor = 'rgba(16, 185, 129, 0.3)';
      setTimeout(() => {
        this.innerHTML = originalHTML;
        this.style.color = '';
        this.style.borderColor = '';
      }, 2000);
    });
  }
});

// Scroll reveal animation
(function() {
  const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);

  document.querySelectorAll('.feature-card, .arch-layer, .cl-item, .visual-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(el);
  });

  document.querySelectorAll('.feature-card').forEach((card, index) => {
    card.style.transitionDelay = `${index * 0.1}s`;
  });

  document.querySelectorAll('.arch-layer').forEach((layer, index) => {
    layer.style.transitionDelay = `${index * 0.15}s`;
  });
})();

// Smooth scroll for nav links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// Nav background on scroll
(function() {
  const nav = document.querySelector('.nav');
  window.addEventListener('scroll', () => {
    if (window.pageYOffset > 50) {
      nav.style.boxShadow = '0 4px 30px rgba(0, 0, 0, 0.3)';
    } else {
      nav.style.boxShadow = 'none';
    }
  });
})();

// Progress bar animation on scroll
(function() {
  const progressBar = document.createElement('div');
  progressBar.className = 'liquid-progress';
  progressBar.style.cssText = 'position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,#00d4ff,#a855f7,#f472b6);z-index:1000;transition:width 0.1s ease-out;width:0%;box-shadow:0 0 10px rgba(0,212,255,0.5);';
  document.body.appendChild(progressBar);

  window.addEventListener('scroll', () => {
    const scrollTop = window.pageYOffset;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = (scrollTop / docHeight) * 100;
    progressBar.style.width = progress + '%';
  });
})();

console.log('%cMindForge', 'font-size:24px;font-weight:bold;background:linear-gradient(135deg,#00d4ff,#a855f7,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;');
console.log('%cAI Agent | Liquid Glass UI', 'font-size:14px;color:#a0a0b0;');


// ========== Liquid Glass System UI ==========

// 1. Nav - dynamic blur intensification on scroll
(function() {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  let ticking = false;
  window.addEventListener('scroll', function() {
    if (!ticking) {
      requestAnimationFrame(function() {
        if (window.scrollY > 20) {
          nav.classList.add('scrolled');
        } else {
          nav.classList.remove('scrolled');
        }
        ticking = false;
      });
      ticking = true;
    }
  });
})();

// 2. Fade-in on scroll
(function() {
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) entry.target.classList.add('visible');
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  document.querySelectorAll('.feature-card, .arch-layer, .cl-item, .visual-card, .section-head').forEach(function(el) {
    el.classList.add('fade-in');
    observer.observe(el);
  });
})();

// 3. Specular highlight - mouse-tracking light reflection on glass surfaces
(function() {
  document.querySelectorAll('.feature-card, .visual-card, .glass-card, .hero-stats, .arch-layer').forEach(function(card) {
    card.addEventListener('mousemove', function(e) {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', x + 'px');
      card.style.setProperty('--mouse-y', y + 'px');
      card.style.setProperty('--mouse-x-pct', (x / rect.width * 100) + '%');
      card.style.setProperty('--mouse-y-pct', (y / rect.height * 100) + '%');
    });
    card.addEventListener('mouseleave', function() {
      card.style.removeProperty('--mouse-x');
      card.style.removeProperty('--mouse-y');
    });
  });
})();

// 4. 3D tilt on feature cards
(function() {
  document.querySelectorAll('.feature-card').forEach(function(card) {
    card.addEventListener('mousemove', function(e) {
      const rect = card.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      var rx = (e.clientY - cy) / (rect.height / 2) * -6;
      var ry = (e.clientX - cx) / (rect.width / 2) * 6;
      card.style.setProperty('--tilt-x', rx + 'deg');
      card.style.setProperty('--tilt-y', ry + 'deg');
    });
    card.addEventListener('mouseleave', function() {
      card.style.setProperty('--tilt-x', '0deg');
      card.style.setProperty('--tilt-y', '0deg');
    });
  });
})();

// 5. Liquid magnetic buttons
(function() {
  document.querySelectorAll('.btn-primary, .btn-solid, .btn-secondary').forEach(function(btn) {
    btn.addEventListener('mousemove', function(e) {
      var rect = btn.getBoundingClientRect();
      var x = e.clientX - rect.left - rect.width / 2;
      var y = e.clientY - rect.top - rect.height / 2;
      btn.style.transform = 'translate(' + (x * 0.15) + 'px, ' + (y * 0.15 - 2) + 'px)';
      btn.style.setProperty('--mouse-x-pct', ((e.clientX - rect.left) / rect.width * 100) + '%');
      btn.style.setProperty('--mouse-y-pct', ((e.clientY - rect.top) / rect.height * 100) + '%');
    });
    btn.addEventListener('mouseleave', function() {
      btn.style.transform = '';
    });
  });
})();

// 6. Liquid ripple on click
(function() {
  document.querySelectorAll('.btn-primary, .btn-solid, .btn-secondary, .nav-links a').forEach(function(el) {
    el.addEventListener('click', function(e) {
      var rect = el.getBoundingClientRect();
      var ripple = document.createElement('span');
      ripple.className = 'liquid-ripple';
      ripple.style.left = (e.clientX - rect.left) + 'px';
      ripple.style.top = (e.clientY - rect.top) + 'px';
      el.appendChild(ripple);
      setTimeout(function() { ripple.remove(); }, 800);
    });
  });
})();

// 7. Parallax depth on hero glow
(function() {
  var heroGlow = document.querySelector('.hero-glow');
  if (!heroGlow) return;
  document.addEventListener('mousemove', function(e) {
    var x = (e.clientX / window.innerWidth - 0.5) * 30;
    var y = (e.clientY / window.innerHeight - 0.5) * 30;
    heroGlow.style.transform = 'translate(calc(-50% + ' + x + 'px), calc(-50% + ' + y + 'px))';
  });
})();
