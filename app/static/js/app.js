async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

async function postJSON(url, data) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return res.json();
}

async function putJSON(url, data) {
    const res = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return res.json();
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
        ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function badge(text, type) {
    return `<span class="badge badge-${type}">${text}</span>`;
}

function statusBadge(status) {
    const map = {
        'pending': 'warning',
        'confirmed': 'info',
        'delivered': 'success',
        'cancelled': 'danger',
        'completed': 'success',
        'open': 'danger',
        'resolved': 'success',
    };
    return badge(status, map[status] || 'info');
}

function showModal(id) {
    document.getElementById(id).classList.add('active');
}

function hideModal(id) {
    document.getElementById(id).classList.remove('active');
}

// Dashboard
async function loadDashboard() {
    const stats = await fetchJSON('/api/stats');
    const el = document.getElementById('stats-grid');
    if (!el) return;

    el.innerHTML = `
        <div class="stat-card">
            <div class="label">Total Orders</div>
            <div class="value primary">${stats.total_orders}</div>
        </div>
        <div class="stat-card">
            <div class="label">Today's Orders</div>
            <div class="value success">${stats.today_orders}</div>
        </div>
        <div class="stat-card">
            <div class="label">Revenue (QR)</div>
            <div class="value success">${stats.total_revenue.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Calls</div>
            <div class="value primary">${stats.total_calls}</div>
        </div>
        <div class="stat-card">
            <div class="label">Today's Calls</div>
            <div class="value primary">${stats.today_calls}</div>
        </div>
        <div class="stat-card">
            <div class="label">Open Complaints</div>
            <div class="value danger">${stats.open_complaints}</div>
        </div>
        <div class="stat-card">
            <div class="label">Pending Callbacks</div>
            <div class="value warning">${stats.pending_callbacks}</div>
        </div>
        <div class="stat-card">
            <div class="label">Products</div>
            <div class="value">${stats.total_products}</div>
        </div>
        <div class="stat-card">
            <div class="label">Customers</div>
            <div class="value">${stats.total_customers}</div>
        </div>
    `;

    // Load recent orders
    const orders = await fetchJSON('/api/orders?limit=10');
    const tbody = document.getElementById('recent-orders-body');
    if (tbody) {
        if (orders.orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:30px">No orders yet. Orders will appear here once the AI agent starts taking calls.</td></tr>';
        } else {
            tbody.innerHTML = orders.orders.map(o => `
                <tr>
                    <td><strong>${o.order_number}</strong></td>
                    <td>${o.customer_name || '-'}</td>
                    <td>QR ${o.total_amount.toLocaleString()}</td>
                    <td>${o.delivery_schedule || '-'}</td>
                    <td>${statusBadge(o.status)}</td>
                    <td>${formatDate(o.created_at)}</td>
                </tr>
            `).join('');
        }
    }

    // Load recent calls
    const calls = await fetchJSON('/api/call-logs?limit=10');
    const callsBody = document.getElementById('recent-calls-body');
    if (callsBody) {
        if (calls.call_logs.length === 0) {
            callsBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:30px">No calls yet. Call logs will appear here once conversations start.</td></tr>';
        } else {
            callsBody.innerHTML = calls.call_logs.map(c => `
                <tr>
                    <td>${c.customer_name || c.caller_phone || '-'}</td>
                    <td>${c.language || '-'}</td>
                    <td>${c.duration_seconds ? c.duration_seconds + 's' : '-'}</td>
                    <td>${c.summary ? c.summary.substring(0, 60) + '...' : '-'}</td>
                    <td>${c.has_complaint ? badge('Complaint', 'danger') : badge('OK', 'success')}</td>
                    <td>${formatDate(c.created_at)}</td>
                </tr>
            `).join('');
        }
    }
}

// Products
async function loadProducts(search, department) {
    let url = '/api/products?limit=100';
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (department) url += `&department=${encodeURIComponent(department)}`;

    const data = await fetchJSON(url);
    const tbody = document.getElementById('products-body');
    if (!tbody) return;

    tbody.innerHTML = data.products.map(p => `
        <tr>
            <td>${p.code}</td>
            <td>${p.department}</td>
            <td>${p.category}</td>
            <td>${p.description}</td>
            <td>${p.name_alternative || '-'}</td>
            <td>${p.packing}</td>
            <td>${p.uom}</td>
            <td><strong>QR ${p.price}</strong></td>
            <td>${p.own_brand ? badge('Own Brand', 'own-brand') : ''} ${p.priority_pricing ? badge('Priority', 'info') : ''}</td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="editProduct(${p.id})">Edit</button>
            </td>
        </tr>
    `).join('');

    document.getElementById('product-count').textContent = `${data.total} products`;
}

async function loadDepartments() {
    const data = await fetchJSON('/api/departments');
    const sel = document.getElementById('dept-filter');
    if (!sel) return;
    sel.innerHTML = '<option value="">All Departments</option>' +
        data.departments.map(d => `<option value="${d.department}">${d.department} (${d.product_count})</option>`).join('');
}

async function editProduct(id) {
    const p = await fetchJSON(`/api/products/${id}`);
    document.getElementById('edit-product-id').value = p.id;
    document.getElementById('edit-product-desc').value = p.description;
    document.getElementById('edit-product-price').value = p.price;
    document.getElementById('edit-product-alt').value = p.name_alternative || '';
    document.getElementById('edit-product-spec').value = p.specification || '';
    document.getElementById('edit-product-stock').checked = p.stock_available;
    showModal('edit-product-modal');
}

async function saveProduct() {
    const id = document.getElementById('edit-product-id').value;
    await postJSON(`/api/products/${id}`, {
        description: document.getElementById('edit-product-desc').value,
        price: parseFloat(document.getElementById('edit-product-price').value),
        name_alternative: document.getElementById('edit-product-alt').value,
        specification: document.getElementById('edit-product-spec').value,
        stock_available: document.getElementById('edit-product-stock').checked ? 1 : 0,
    });
    hideModal('edit-product-modal');
    loadProducts(
        document.getElementById('product-search')?.value,
        document.getElementById('dept-filter')?.value
    );
}

// Customers
async function loadCustomers(search) {
    let url = '/api/customers';
    if (search) url += `?search=${encodeURIComponent(search)}`;

    const data = await fetchJSON(url);
    const tbody = document.getElementById('customers-body');
    if (!tbody) return;

    tbody.innerHTML = data.customers.map(c => {
        const contacts = c.contact_list.map(ct =>
            `${ct.person}: ${ct.phone}`
        ).join('<br>');
        return `
            <tr>
                <td>${c.customer_code}</td>
                <td><strong>${c.customer_name}</strong></td>
                <td>${c.location}</td>
                <td>${contacts || '-'}</td>
                <td>${c.payment_terms}</td>
                <td>${statusBadge(c.order_status || 'active')}</td>
                <td>
                    <button class="btn btn-sm btn-outline" onclick="editCustomer(${c.id})">Edit</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function addCustomer() {
    const data = {
        customer_code: parseInt(document.getElementById('new-cust-code').value),
        customer_name: document.getElementById('new-cust-name').value,
        location: document.getElementById('new-cust-location').value,
        payment_terms: document.getElementById('new-cust-payment').value,
        contact_person: document.getElementById('new-cust-contact').value,
        phone_number: document.getElementById('new-cust-phone').value,
        calling_time: document.getElementById('new-cust-calltime').value,
    };
    await postJSON('/api/customers', data);
    hideModal('add-customer-modal');
    loadCustomers();
}

// Orders page
async function loadOrdersPage(status) {
    let url = '/api/orders?limit=100';
    if (status) url += `&status=${status}`;

    const data = await fetchJSON(url);
    const tbody = document.getElementById('orders-body');
    if (!tbody) return;

    if (data.orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:30px">No orders found</td></tr>';
        return;
    }

    tbody.innerHTML = data.orders.map(o => `
        <tr onclick="viewOrder(${o.id})" style="cursor:pointer">
            <td><strong>${o.order_number}</strong></td>
            <td>${o.customer_name || '-'} (${o.customer_code || '-'})</td>
            <td>QR ${o.total_amount.toLocaleString()}</td>
            <td>${o.payment_terms}</td>
            <td>${o.delivery_schedule || '-'}</td>
            <td>${statusBadge(o.status)}</td>
            <td>${formatDate(o.created_at)}</td>
        </tr>
    `).join('');
}

async function viewOrder(id) {
    const data = await fetchJSON(`/api/orders/${id}`);
    const o = data.order;
    let html = `
        <p><strong>Order:</strong> ${o.order_number}</p>
        <p><strong>Customer:</strong> ${o.customer_name} (${o.customer_code})</p>
        <p><strong>Caller:</strong> ${o.caller_name || '-'} (${o.caller_phone || '-'})</p>
        <p><strong>Payment:</strong> ${o.payment_terms}</p>
        <p><strong>Delivery:</strong> ${o.delivery_schedule}</p>
        <p><strong>Status:</strong> ${statusBadge(o.status)}</p>
        <hr style="margin:12px 0;border-color:var(--border)">
        <table>
            <thead><tr><th>Product</th><th>Packing</th><th>UOM</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
            <tbody>
    `;
    data.items.forEach(i => {
        html += `<tr><td>${i.product_description}</td><td>${i.packing || '-'}</td><td>${i.uom || '-'}</td>
                 <td>${i.quantity}</td><td>QR ${i.unit_price}</td><td>QR ${i.total_price}</td></tr>`;
    });
    html += `</tbody></table>
        <p style="margin-top:12px;font-weight:700">Total: QR ${o.total_amount.toLocaleString()}</p>`;

    if (o.wallet_discount > 0 || o.wallet_upsell > 0) {
        html += `<p>Wallet Discount: QR ${o.wallet_discount} | Upsell: QR ${o.wallet_upsell} | Balance: QR ${o.wallet_balance}</p>`;
    }
    if (o.notes) html += `<p><strong>Notes:</strong> ${o.notes}</p>`;

    document.getElementById('order-detail-body').innerHTML = html;
    showModal('order-detail-modal');
}

// Calls page
async function loadCallsPage(filter) {
    let url = '/api/call-logs?limit=100';
    if (filter === 'complaints') url += '&has_complaint=true';
    if (filter === 'callbacks') url += '&callback_required=true';

    const data = await fetchJSON(url);
    const tbody = document.getElementById('calls-body');
    if (!tbody) return;

    if (data.call_logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:30px">No call logs found</td></tr>';
        return;
    }

    tbody.innerHTML = data.call_logs.map(c => `
        <tr>
            <td>${c.customer_name || '-'}</td>
            <td>${c.caller_phone || '-'}</td>
            <td>${c.language || '-'}</td>
            <td>${c.duration_seconds ? c.duration_seconds + 's' : '-'}</td>
            <td>${c.summary || '-'}</td>
            <td>
                ${c.has_complaint ? badge('Complaint', 'danger') : ''}
                ${c.callback_required ? badge('Callback', 'warning') : ''}
                ${!c.has_complaint && !c.callback_required ? badge('OK', 'success') : ''}
            </td>
            <td>${formatDate(c.created_at)}</td>
        </tr>
    `).join('');
}
