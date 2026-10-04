/**
 * PocketSmart AI - Client Interaction & Dynamic Planner Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  initToasts();
  initBudgetSliders();
  initDropzone();
  initPlannerForms();
});

// Toast Notification
function showToast(message, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠'}</span> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Synchronize budget sliders and inputs if present
function initBudgetSliders() {
  const budgetInput = document.getElementById('budget');
  const budgetSlider = document.getElementById('budgetSlider');
  if (budgetInput && budgetSlider) {
    budgetInput.addEventListener('input', (e) => {
      budgetSlider.value = e.target.value;
    });
    budgetSlider.addEventListener('input', (e) => {
      budgetInput.value = e.target.value;
    });
  }
}

// File dropzone & image preview
function initDropzone() {
  const dropzone = document.getElementById('imageDropzone');
  const fileInput = document.getElementById('imageInput');
  const previewWrap = document.getElementById('imagePreviewWrap');
  const previewImg = document.getElementById('imagePreview');
  const removeBtn = document.getElementById('removeImageBtn');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      fileInput.files = e.dataTransfer.files;
      handleFileSelected(fileInput.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  if (removeBtn) {
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.value = '';
      if (previewWrap) previewWrap.style.display = 'none';
      dropzone.style.display = 'block';
    });
  }

  function handleFileSelected(file) {
    if (!file.type.startsWith('image/')) {
      showToast('Please select a valid image file (JPG, PNG, WEBP)', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      if (previewImg) previewImg.src = e.target.result;
      if (previewWrap) previewWrap.style.display = 'block';
      dropzone.style.display = 'none';
    };
    reader.readAsDataURL(file);
  }
}

// Dynamic Steps for AI Loading
function startLoadingStepCycle(statusElement) {
  const steps = [
    "Analyzing preferences and project requirements...",
    "Consulting Gemini neural design models...",
    "Synthesizing optimal budget breakdowns...",
    "Sourcing curated piece recommendations & styling tips...",
    "Polishing final custom plan..."
  ];
  let idx = 0;
  if (statusElement) statusElement.textContent = steps[0];
  return setInterval(() => {
    idx = (idx + 1) % steps.length;
    if (statusElement) statusElement.textContent = steps[idx];
  }, 2200);
}

// Planner Forms handling
function initPlannerForms() {
  const form = document.querySelector('.planner-form');
  if (!form) return;

  const plannerType = form.dataset.plannerType; // "home", "party", "jewelry"
  const loadingOverlay = document.getElementById('loadingOverlay');
  const loadingStatus = document.getElementById('loadingStatus');
  const resultsContainer = document.getElementById('resultsContainer');
  const submitBtn = form.querySelector('button[type="submit"]');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (submitBtn) submitBtn.disabled = true;
    if (loadingOverlay) loadingOverlay.style.display = 'flex';
    if (resultsContainer) resultsContainer.style.display = 'none';

    const cycleId = startLoadingStepCycle(loadingStatus);

    try {
      let response;
      if (plannerType === 'jewelry') {
        const formData = new FormData(form);
        response = await fetch('/api/generate-jewelry', {
          method: 'POST',
          credentials: 'include',
          body: formData
        });
      } else {
        const formData = new FormData(form);
        const jsonBody = {};
        formData.forEach((value, key) => {
          if (key === 'budget' || key === 'room_size_sqft') {
            jsonBody[key] = parseFloat(value) || 0;
          } else if (key === 'guest_count') {
            jsonBody[key] = parseInt(value, 10) || 1;
          } else {
            jsonBody[key] = value;
          }
        });

        const endpoint = plannerType === 'home' ? '/api/generate-home' : '/api/generate-party';
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(jsonBody)
        });
      }

      clearInterval(cycleId);

      if (!response.ok) {
        if (response.status === 401) {
          showToast('Please log in to generate your plan.', 'error');
          setTimeout(() => window.location.href = '/login', 1500);
          return;
        }
        const errData = await response.json().catch(() => ({ detail: 'Failed to generate plan' }));
        throw new Error(errData.detail || 'Failed to generate plan');
      }

      const data = await response.json();
      renderResults(data, plannerType);
      showToast('AI Plan generated successfully!');

      if (resultsContainer) {
        resultsContainer.style.display = 'block';
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (err) {
      clearInterval(cycleId);
      console.error(err);
      showToast(err.message || 'An error occurred while generating the plan.', 'error');
    } finally {
      if (loadingOverlay) loadingOverlay.style.display = 'none';
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

function renderResults(data, plannerType) {
  // Title & Summary
  const titleEl = document.getElementById('resTitle');
  const summaryEl = document.getElementById('resSummary');
  if (titleEl) titleEl.textContent = data.title || "Smart Plan Results";
  if (summaryEl) summaryEl.textContent = data.summary || "";

  // Metrics
  const cur = data.currency || "$";
  const totalBudgetEl = document.getElementById('resTotalBudget');
  const estimatedEl = document.getElementById('resEstimatedTotal');
  const bufferEl = document.getElementById('resSavingsBuffer');

  if (totalBudgetEl) totalBudgetEl.textContent = `${cur}${Number(data.total_budget || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  if (estimatedEl) estimatedEl.textContent = `${cur}${Number(data.estimated_total || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  if (bufferEl) bufferEl.textContent = `${cur}${Number(data.savings_buffer || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

  // Jewelry Specific Blocks
  const jewelryBlock = document.getElementById('jewelrySpecificBlock');
  if (jewelryBlock) {
    if (plannerType === 'jewelry') {
      jewelryBlock.style.display = 'block';
      const metalEl = document.getElementById('resMetal');
      const gemEl = document.getElementById('resGemstone');
      const outfitEl = document.getElementById('resOutfitAnalysis');
      const verdictEl = document.getElementById('resVerdict');
      if (metalEl) metalEl.textContent = data.metal_recommendation || "Warm Gold / Vermeil";
      if (gemEl) gemEl.textContent = data.gemstone_or_finish || "Cultured Pearls & Diamonds";
      if (outfitEl) outfitEl.textContent = data.outfit_analysis || "";
      if (verdictEl) verdictEl.textContent = data.styling_verdict || "";
    } else {
      jewelryBlock.style.display = 'none';
    }
  }

  // Categories Grid
  const catGrid = document.getElementById('categoriesGrid');
  if (catGrid && data.categories) {
    catGrid.innerHTML = data.categories.map(cat => `
      <div class="glass-panel category-card">
        <div class="category-header">
          <div class="category-name">${escapeHtml(cat.name)}</div>
          <div class="category-badge">${cur}${Number(cat.allocated_budget || 0).toLocaleString()} (${cat.percentage || 0}%)</div>
        </div>
        <div class="item-list">
          ${(cat.items || []).map(item => `
            <div class="item-card">
              <div class="item-row">
                <span class="item-name">${escapeHtml(item.name)}</span>
                <span class="item-price">${cur}${Number(item.estimated_cost || 0).toLocaleString()}</span>
              </div>
              <div class="item-desc">${escapeHtml(item.description || '')}</div>
              ${item.smart_tip ? `
                <div class="item-tip">
                  <span>💡</span> <span>${escapeHtml(item.smart_tip)}</span>
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }

  // AI Tips
  const tipsList = document.getElementById('aiTipsList');
  if (tipsList && data.ai_tips) {
    tipsList.innerHTML = data.ai_tips.map(tip => `<li>${escapeHtml(tip)}</li>`).join('');
  }

  // Action Timeline / Phases
  const timelineList = document.getElementById('timelineList');
  if (timelineList && data.timeline_or_phases) {
    timelineList.innerHTML = data.timeline_or_phases.map((phase, idx) => `
      <div class="item-card" style="margin-bottom: 0.75rem;">
        <span style="color: #a5b4fc; font-weight: 700; margin-right: 0.5rem;">${idx + 1}.</span>
        <span>${escapeHtml(phase)}</span>
      </div>
    `).join('');
  }

  // View full recommendation link if ID is returned
  const viewDetailBtn = document.getElementById('viewDetailBtn');
  if (viewDetailBtn && data.id) {
    viewDetailBtn.href = `/recommendation/${data.id}`;
    viewDetailBtn.style.display = 'inline-flex';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
