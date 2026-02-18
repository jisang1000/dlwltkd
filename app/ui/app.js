const metricsNode = document.querySelector('#metrics');
const tableBody = document.querySelector('#appointments-body');
const form = document.querySelector('#appointment-form');
const message = document.querySelector('#form-message');
const reloadBtn = document.querySelector('#reload');

const fmt = new Intl.NumberFormat('ko-KR');

const renderMetrics = (summary) => {
  const items = [
    ['총 예약', summary.today_total_appointments],
    ['완료 예약', summary.today_completed_appointments],
    ['취소율', `${(summary.today_cancellation_rate * 100).toFixed(1)}%`],
    ['예상 매출', `${fmt.format(summary.today_estimated_revenue)}원`],
  ];

  metricsNode.innerHTML = items
    .map(
      ([label, value]) => `
      <div class="metric-item">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
      </div>
    `,
    )
    .join('');
};

const renderAppointments = (rows) => {
  tableBody.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td>${row.customer_id}</td>
        <td>${row.stylist_id}</td>
        <td>${row.service_id}</td>
        <td>${new Date(row.starts_at).toLocaleString('ko-KR')}</td>
        <td><span class="status">${row.status}</span></td>
      </tr>
    `,
    )
    .join('');
};

const loadDashboard = async () => {
  const [summaryRes, appointmentsRes] = await Promise.all([
    fetch('/dashboard/summary'),
    fetch('/appointments?limit=20'),
  ]);

  if (!summaryRes.ok || !appointmentsRes.ok) {
    throw new Error('데이터 조회에 실패했습니다.');
  }

  const [summary, appointments] = await Promise.all([summaryRes.json(), appointmentsRes.json()]);
  renderMetrics(summary);
  renderAppointments(appointments);
};

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = 'message';
  message.textContent = '';

  const formData = new FormData(form);
  const payload = {
    customer_id: Number(formData.get('customer_id')),
    stylist_id: Number(formData.get('stylist_id')),
    service_id: Number(formData.get('service_id')),
    starts_at: new Date(String(formData.get('starts_at'))).toISOString(),
    notes: String(formData.get('notes') || ''),
  };

  try {
    const res = await fetch('/appointments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const body = await res.json();
      throw new Error(body.detail || '예약 저장 실패');
    }

    message.classList.add('ok');
    message.textContent = '예약이 생성되었습니다.';
    form.reset();
    await loadDashboard();
  } catch (error) {
    message.classList.add('error');
    message.textContent = error instanceof Error ? error.message : '오류가 발생했습니다.';
  }
});

reloadBtn.addEventListener('click', () => {
  loadDashboard().catch((error) => {
    message.className = 'message error';
    message.textContent = error instanceof Error ? error.message : '오류가 발생했습니다.';
  });
});

loadDashboard().catch((error) => {
  message.className = 'message error';
  message.textContent = error instanceof Error ? error.message : '초기 로드 실패';
});
