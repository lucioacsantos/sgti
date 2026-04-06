// =========================
// CONFIG
// =========================
const API_URL = '/api'

// =========================
// AUTH
// =========================
function getAuthToken() {
  return localStorage.getItem('auth_token') || 'dev-token'
}

function setAuthToken(token) {
  localStorage.setItem('auth_token', token)
}

function logout() {
  localStorage.removeItem('auth_token')
  location.reload()
}

// =========================
// API WRAPPER
// =========================
async function apiFetch(url, options = {}) {
  const token = getAuthToken()

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      'Authorization': `Bearer ${token}`
    }
  })

  if (!response.ok) {
    const text = await response.text()
    console.error("Erro API:", text)
    alert(`Erro ${response.status}`)
    throw new Error(text)
  }

  return response.json()
}

// =========================
// ASSETS
// =========================
window.loadAssets = async function () {
  const tbody = document.getElementById('assetsTableBody')
  tbody.innerHTML = '<tr><td colspan="6">Carregando...</td></tr>'

  try {
    const search = document.getElementById('searchInput').value

    let url = `${API_URL}/ativos/`
    if (search) url += `?search=${encodeURIComponent(search)}`

    const assets = await apiFetch(url)

    tbody.innerHTML = assets.map(a => `
      <tr>
        <td>${a.id}</td>
        <td>${a.nome}</td>
        <td>${a.tipo}</td>
        <td>${a.descricao || ''}</td>
        <td>${a.responsavel}</td>
        <td>
          <button class="btn btn-sm btn-warning" onclick="editAsset(${a.id})">Editar</button>
          <button class="btn btn-sm btn-danger" onclick="deleteAsset(${a.id})">Excluir</button>
        </td>
      </tr>
    `).join('')
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6">Erro ao carregar</td></tr>'
  }
}

// =========================
// SAVE ASSET
// =========================
window.saveAsset = async function () {
  const id = document.getElementById('assetId').value

  const payload = {
    nome: document.getElementById('assetName').value,
    tipo: document.getElementById('assetType').value,
    descricao: document.getElementById('assetDescription').value,
    responsavel: document.getElementById('assetOwner').value
  }

  try {
    if (id) {
      await apiFetch(`${API_URL}/ativos/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      })
    } else {
      await apiFetch(`${API_URL}/ativos/`, {
        method: 'POST',
        body: JSON.stringify(payload)
      })
    }

    bootstrap.Modal.getInstance(document.getElementById('assetModal')).hide()
    loadAssets()
  } catch {}
}

// =========================
// DELETE
// =========================
window.deleteAsset = async function (id) {
  if (!confirm("Confirma exclusão?")) return

  try {
    await apiFetch(`${API_URL}/ativos/${id}`, { method: 'DELETE' })
    loadAssets()
  } catch {}
}

// =========================
// RELATIONSHIPS
// =========================
window.loadRelationships = async function () {
  const tbody = document.getElementById('relationshipsTableBody')

  try {
    const rels = await apiFetch(`${API_URL}/relacionamentos/`)

    tbody.innerHTML = rels.map(r => `
      <tr>
        <td>${r.ativo_origem.nome}</td>
        <td>${r.tipo_relacionamento}</td>
        <td>${r.ativo_destino.nome}</td>
        <td>
          <button class="btn btn-danger btn-sm" onclick="deleteRelationship(${r.id_ativo_origem}, ${r.id_ativo_destino})">Excluir</button>
        </td>
      </tr>
    `).join('')
  } catch {
    tbody.innerHTML = '<tr><td colspan="4">Erro</td></tr>'
  }
}

// =========================
// SERVICES
// =========================
window.loadServices = async function () {
  const tbody = document.getElementById('servicesTableBody')

  try {
    const services = await apiFetch(`${API_URL}/servicos/`)

    tbody.innerHTML = services.map(s => `
      <tr>
        <td>${s.id}</td>
        <td>${s.nome_servico}</td>
        <td>${s.tipo_servico}</td>
        <td>${s.hosts.map(h => h.nome).join(', ')}</td>
        <td></td>
      </tr>
    `).join('')
  } catch {
    tbody.innerHTML = '<tr><td colspan="5">Erro</td></tr>'
  }
}

// =========================
// INIT
// =========================
document.addEventListener("DOMContentLoaded", () => {
  loadAssets()
})