import './style.css'

window.bootstrap = bootstrap;

const API_URL = '/api';


window.openAssetModal = function() {
  document.getElementById('assetModalTitle').innerText = 'Novo Ativo'
  document.getElementById('assetForm').reset()
  document.getElementById('assetId').value = ''
}

window.loadAssets = async function() {
  try {
    const filterType = document.getElementById('filterType').value
    const filterOwner = document.getElementById('filterOwner').value
    
    let url = `${API_URL}/assets/`
    const params = new URLSearchParams()
    if (filterType) params.append('type', filterType)
    if (filterOwner) params.append('owner', filterOwner)
    if (params.toString()) url += '?' + params.toString()
    
    const response = await fetch(url)
    const assets = await response.json()
    
    const tbody = document.getElementById('assetsTableBody')
    if (assets.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center">Nenhum ativo encontrado</td></tr>'
      return
    }
    
    tbody.innerHTML = assets.map(asset => `
      <tr>
        <td>${asset.id}</td>
        <td>${asset.name}</td>
        <td><span class="badge bg-info">${asset.type}</span></td>
        <td>${asset.description || '-'}</td>
        <td>${asset.owner}</td>
        <td>
          <button class="btn btn-sm btn-warning" onclick="editAsset(${asset.id})">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-danger" onclick="deleteAsset(${asset.id})">
            <i class="bi bi-trash"></i>
          </button>
          <button class="btn btn-sm btn-info" onclick="viewAssetRelationships(${asset.id})">
            <i class="bi bi-diagram-2"></i>
          </button>
        </td>
      </tr>
    `).join('')
  } catch (error) {
    console.error('Erro ao carregar ativos:', error)
    const tbody = document.getElementById('assetsTableBody')
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Erro ao carregar ativos. Verifique se o backend está rodando.</td></tr>'
  }
}

window.editAsset = async function(id) {
  try {
    const response = await fetch(`${API_URL}/assets/${id}`)
    const asset = await response.json()
    
    document.getElementById('assetModalTitle').innerText = 'Editar Ativo'
    document.getElementById('assetId').value = asset.id
    document.getElementById('assetName').value = asset.name
    document.getElementById('assetType').value = asset.type
    document.getElementById('assetDescription').value = asset.description || ''
    document.getElementById('assetOwner').value = asset.owner
    
    const modal = new bootstrap.Modal(document.getElementById('assetModal'))
    modal.show()
  } catch (error) {
    console.error('Erro ao carregar ativo:', error)
    alert('Erro ao carregar ativo')
  }
}

window.saveAsset = async function() {
  const id = document.getElementById('assetId').value
  const asset = {
    name: document.getElementById('assetName').value,
    type: document.getElementById('assetType').value,
    description: document.getElementById('assetDescription').value || null,
    owner: document.getElementById('assetOwner').value
  }
  
  if (!asset.name || !asset.type || !asset.owner) {
    alert('Por favor, preencha todos os campos obrigatórios')
    return
  }
  
  try {
    let response
    if (id) {
      response = await fetch(`${API_URL}/assets/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asset)
      })
    } else {
      response = await fetch(`${API_URL}/assets/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asset)
      })
    }
    
    if (response.ok) {
      const modal = bootstrap.Modal.getInstance(document.getElementById('assetModal'))
      modal.hide()
      await loadAssets()
      alert(id ? 'Ativo atualizado com sucesso!' : 'Ativo criado com sucesso!')
    } else {
      const error = await response.json()
      alert('Erro ao salvar ativo: ' + JSON.stringify(error))
    }
  } catch (error) {
    console.error('Erro ao salvar ativo:', error)
    alert('Erro ao salvar ativo. Verifique se o backend está rodando.')
  }
}

window.deleteAsset = async function(id) {
  if (!confirm('Tem certeza que deseja deletar este ativo?')) return
  
  try {
    const response = await fetch(`${API_URL}/assets/${id}`, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      await loadAssets()
      alert('Ativo deletado com sucesso!')
    } else {
      alert('Erro ao deletar ativo')
    }
  } catch (error) {
    console.error('Erro ao deletar ativo:', error)
    alert('Erro ao deletar ativo')
  }
}

window.viewAssetRelationships = async function(id) {
  try {
    const response = await fetch(`${API_URL}/assets/${id}`)
    const asset = await response.json()
    
    let message = `Relacionamentos do ativo: ${asset.name}\n\n`
    if (asset.related_to && asset.related_to.length > 0) {
      message += 'Relacionado com:\n'
      asset.related_to.forEach(rel => {
        message += `- ${rel.name} (${rel.type})\n`
      })
    } else {
      message += 'Nenhum relacionamento encontrado.'
    }
    
    alert(message)
  } catch (error) {
    console.error('Erro ao carregar relacionamentos:', error)
    alert('Erro ao carregar relacionamentos')
  }
}

window.loadRelationships = async function() {
  try {
    const response = await fetch(`${API_URL}/relationships/`)
    const relationships = await response.json()
    
    const tbody = document.getElementById('relationshipsTableBody')
    if (relationships.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum relacionamento encontrado</td></tr>'
      return
    }
    
    tbody.innerHTML = relationships.map(rel => `
      <tr>
        <td>
          <strong>${rel.source_asset.name}</strong>
          <br><small class="text-muted">${rel.source_asset.type}</small>
        </td>
        <td>
          <span class="badge bg-success">${rel.relationship_type}</span>
        </td>
        <td>
          <strong>${rel.target_asset.name}</strong>
          <br><small class="text-muted">${rel.target_asset.type}</small>
        </td>
        <td>
          <button class="btn btn-sm btn-danger" onclick="deleteRelationship(${rel.source_asset_id}, ${rel.target_asset_id})">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `).join('')
  } catch (error) {
    console.error('Erro ao carregar relacionamentos:', error)
    const tbody = document.getElementById('relationshipsTableBody')
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Erro ao carregar relacionamentos. Verifique se o backend está rodando.</td></tr>'
  }
}

window.loadAssetsForRelationship = async function() {
  try {
    const response = await fetch(`${API_URL}/assets/`)
    const assets = await response.json()
    
    const sourceSelect = document.getElementById('sourceAssetId')
    const targetSelect = document.getElementById('targetAssetId')
    
    const options = assets.map(asset => 
      `<option value="${asset.id}">${asset.name} (${asset.type})</option>`
    ).join('')
    
    sourceSelect.innerHTML = '<option value="">Selecione...</option>' + options
    targetSelect.innerHTML = '<option value="">Selecione...</option>' + options
  } catch (error) {
    console.error('Erro ao carregar ativos:', error)
    alert('Erro ao carregar ativos para relacionamento')
  }
}

window.saveRelationship = async function() {
  const relationship = {
    source_asset_id: parseInt(document.getElementById('sourceAssetId').value),
    target_asset_id: parseInt(document.getElementById('targetAssetId').value),
    relationship_type: document.getElementById('relationshipType').value
  }
  
  if (!relationship.source_asset_id || !relationship.target_asset_id || !relationship.relationship_type) {
    alert('Por favor, preencha todos os campos')
    return
  }
  
  try {
    const response = await fetch(`${API_URL}/relationships/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(relationship)
    })
    
    if (response.ok) {
      const modal = bootstrap.Modal.getInstance(document.getElementById('relationshipModal'))
      modal.hide()
      document.getElementById('relationshipForm').reset()
      await loadRelationships()
      alert('Relacionamento criado com sucesso!')
    } else {
      const error = await response.json()
      alert('Erro ao criar relacionamento: ' + error.detail)
    }
  } catch (error) {
    console.error('Erro ao criar relacionamento:', error)
    alert('Erro ao criar relacionamento. Verifique se o backend está rodando.')
  }
}

window.deleteRelationship = async function(sourceId, targetId) {
  if (!confirm('Tem certeza que deseja deletar este relacionamento?')) return
  
  try {
    const response = await fetch(`${API_URL}/relationships/${sourceId}/${targetId}`, {
      method: 'DELETE'
    })
    
    if (response.ok) {
      await loadRelationships()
      alert('Relacionamento deletado com sucesso!')
    } else {
      alert('Erro ao deletar relacionamento')
    }
  } catch (error) {
    console.error('Erro ao deletar relacionamento:', error)
    alert('Erro ao deletar relacionamento')
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadAssets()
  
  const relationshipsTab = document.getElementById('relationships-tab')
  relationshipsTab.addEventListener('click', () => {
    loadRelationships()
  })
})

/* -----------------------
      Mapa CMDB
------------------------ */

let globalData = [];
let filterTypes = new Set();

const COLOR_BY_TYPE = {
  "Máquina Virtual": "#ff7777",
  "Container": "#ffaa77",
  "Switch": "#77aaff",
  "Aplicativo": "#aaff77",
  "Banco de Dados": "#aa77ff",
  "Servidor": "#ffcc00",
  "Firewall": "#00ccaa",
  "default": "#cccccc"
};

window.loadGraph = async function () {
  const resp = await fetch(`${API_URL}/relationships`);
  globalData = await resp.json();

  filterTypes = new Set(globalData.flatMap(r => [
    r.source_asset.type,
    r.target_asset.type
  ]));

  renderFilters();
  buildGraph();
}

function renderFilters() {
  const container = document.getElementById("filters");
  container.innerHTML = "";

  filterTypes.forEach(type => {
    container.innerHTML += `
      <label>
        <input type="checkbox" class="fcheck" checked value="${type}" onchange="buildGraph()">
        ${type}
      </label> &nbsp;
    `;
  });
}

window.buildGraph = function () {
  const layoutMode = document.getElementById("layoutSelect").value;

  const nodesMap = new Map();
  const edges = [];

  globalData.forEach(rel => {

    function makeNode(asset) {
      return {
        id: asset.id,
        label: asset.name,
        type: asset.type,
        owner: asset.owner,
        description: asset.description,
        color: COLOR_BY_TYPE[asset.type] || COLOR_BY_TYPE.default,
        shape: "box"
      };
    }

    nodesMap.set(rel.source_asset.id, makeNode(rel.source_asset));
    nodesMap.set(rel.target_asset.id, makeNode(rel.target_asset));

    edges.push({
      from: rel.source_asset_id,
      to: rel.target_asset_id,
      label: rel.relationship_type,
      arrows: "to"
    });
  });

  const activeFilters = [...document.querySelectorAll(".fcheck")]
    .filter(c => c.checked)
    .map(c => c.value);

  const filteredNodes = [...nodesMap.values()].filter(n => activeFilters.includes(n.type));

  renderNetwork(filteredNodes, edges, layoutMode);
}

function renderNetwork(nodes, edges, layoutMode) {

  const container = document.getElementById("network");
  if (!container) return;

  const data = {
    nodes: new vis.DataSet(nodes),
    edges: new vis.DataSet(edges),
  };

  const options = {
    layout: layoutMode === "hierarchical"
      ? { hierarchical: { direction: "LR", sortMethod: "directed" } }
      : {},

    physics: layoutMode === "force"
      ? { enabled: true, solver: "forceAtlas2Based" }
      : { enabled: false }
  };

  const network = new vis.Network(container, data, options);

  network.on("doubleClick", p => {
    if (p.nodes.length > 0) {
      const id = p.nodes[0];
      const node = nodes.find(n => n.id === id);
      openMapModal(node);
    }
  });
}

function openMapModal(n) {
  document.getElementById("mapModalTitle").innerText = n.label;
  document.getElementById("mapModalType").innerText = n.type;
  document.getElementById("mapModalOwner").innerText = n.owner;
  document.getElementById("mapModalDesc").innerText = n.description;

  new bootstrap.Modal(document.getElementById("mapModal")).show();
}

/* -----------------------
    EVENTOS DE ABAS
------------------------ */

document.addEventListener("DOMContentLoaded", () => {
  loadAssets(); // aba inicial

  const relationshipsTab = document.getElementById('relationships-tab');
  relationshipsTab.addEventListener("shown.bs.tab", () => loadRelationships());

  const mapTab = document.getElementById("map-tab");
  mapTab.addEventListener("shown.bs.tab", () => {
    setTimeout(() => loadGraph(), 200);
  });
});

// ==== Serviços (CRUD) ====
const SERVICE_URL = `${API_URL}/services`;

// Abre modal limpo para novo serviço
window.openServiceModal = async function() {
  document.getElementById('serviceForm').reset();
  document.getElementById('serviceId').value = '';
  document.getElementById('serviceModalTitle').innerText = 'Novo Serviço';

  // Carrega lista de assets para o select
  await populateAssetsSelect();
  // mostra modal
  new window.bootstrap.Modal(document.getElementById('serviceModal')).show();

  // Reset button handler
  const btn = document.getElementById('serviceSaveBtn');
  btn.onclick = saveService;
}

// Preenche select de hosts com assets existentes
async function populateAssetsSelect() {
    const types = ["Máquina Virtual", "Servidor"];

    const query = types
        .map(type => `type=${encodeURIComponent(type)}`)
        .join("&");

    const res = await fetch(`${API_URL}/assets/?${query}`);
    const assets = await res.json();

    const sel = document.getElementById('servico_hosts');
    sel.innerHTML = "";

    assets.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.text = `${a.name} (${a.type})`;
        sel.appendChild(opt);
    });
}


// Carrega lista de serviços e renderiza tabela
window.loadServices = async function() {
  try {
    const res = await fetch(SERVICE_URL);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Erro ao listar serviços');
    }
    const services = await res.json();
    const tbody = document.getElementById('servicesTableBody');

    if (!services || services.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhum serviço cadastrado</td></tr>';
      return;
    }

    tbody.innerHTML = services.map(s => {
      const hosts = (s.hosts || []).map(h => h.name).join(', ');
      return `
        <tr>
          <td>${s.id}</td>
          <td>${escapeHtml(s.nome_servico || s.name || '')}</td>
          <td>${escapeHtml(s.tipo_servico || '')}</td>
          <td>${escapeHtml(hosts)}</td>
          <td>
            <button class="btn btn-sm btn-warning" onclick="editService(${s.id})"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-danger" onclick="deleteService(${s.id})"><i class="bi bi-trash"></i></button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Erro ao carregar serviços:', err);
    const tbody = document.getElementById('servicesTableBody');
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Erro ao carregar serviços</td></tr>`;
  }
}

// Editar (carrega dados no modal)
window.editService = async function(id) {
  try {
    const res = await fetch(`${SERVICE_URL}/${id}`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Erro ao buscar serviço');
    }
    const s = await res.json();

    document.getElementById('serviceId').value = s.id;
    document.getElementById('tipo_servico').value = s.tipo_servico || '';
    document.getElementById('nome_servico').value = s.nome_servico || '';
    document.getElementById('servico_stop').value = s.servico_stop || '';
    document.getElementById('servico_start').value = s.servico_start || '';
    document.getElementById('servico_validacao').value = s.servico_validacao || '';
    document.getElementById('servico_usuario').value = s.servico_usuario || '';

    await populateAssetsSelect();

    // Seleciona os hosts que já existem
    const sel = document.getElementById('servico_hosts');
    const hostIds = (s.hosts || []).map(h => String(h.id));
    for (let i = 0; i < sel.options.length; i++) {
      const opt = sel.options[i];
      opt.selected = hostIds.includes(opt.value);
    }

    document.getElementById('serviceModalTitle').innerText = 'Editar Serviço';
    new window.bootstrap.Modal(document.getElementById('serviceModal')).show();

    document.getElementById('serviceSaveBtn').onclick = saveService;

  } catch (err) {
    console.error('Erro ao carregar serviço:', err);
    alert('Erro ao carregar serviço: ' + (err.message || 'ver logs'));
  }
}

// Salvar (create ou update)
async function saveService() {
  const id = document.getElementById('serviceId').value;
  const payload = {
    tipo_servico: document.getElementById('tipo_servico').value,
    nome_servico: document.getElementById('nome_servico').value,
    servico_stop: document.getElementById('servico_stop').value,
    servico_start: document.getElementById('servico_start').value,
    servico_validacao: document.getElementById('servico_validacao').value || null,
    servico_usuario: document.getElementById('servico_usuario').value,
    host_ids: Array.from(document.getElementById('servico_hosts').selectedOptions).map(o => parseInt(o.value))
  };

  // validações simples
  if (!payload.tipo_servico || !payload.nome_servico || !payload.servico_stop || !payload.servico_start || !payload.servico_usuario) {
    alert('Preencha todos os campos obrigatórios');
    return;
  }

  try {
    let res;
    if (id) {
      res = await fetch(`${SERVICE_URL}/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch(SERVICE_URL, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
    }

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Erro ao salvar serviço');
    }

    // fecha modal
    const modalEl = document.getElementById('serviceModal');
    const modalInst = window.bootstrap.Modal.getInstance(modalEl);
    if (modalInst) modalInst.hide();
    else console.warn('Modal instance não encontrada');

    await loadServices();
    alert(id ? 'Serviço atualizado com sucesso' : 'Serviço criado com sucesso');

  } catch (err) {
    console.error('Erro ao salvar serviço:', err);
    alert('Erro ao salvar serviço: ' + (err.message || 'ver logs'));
  }
}

// Deletar serviço
window.deleteService = async function(id) {
  if (!confirm('Confirma exclusão do serviço?')) return;
  try {
    const res = await fetch(`${SERVICE_URL}/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Erro ao deletar serviço');
    }
    await loadServices();
    alert('Serviço excluído');
  } catch (err) {
    console.error('Erro ao deletar serviço:', err);
    alert('Erro ao deletar serviço: ' + (err.message || 'ver logs'));
  }
}

// Pequena função utilitária para escapar HTML ao renderizar texto
function escapeHtml(unsafe) {
  if (!unsafe && unsafe !== 0) return '';
  return String(unsafe)
    .replaceAll('&', "&amp;")
    .replaceAll('<', "&lt;")
    .replaceAll('>', "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// === Integrar com evento da aba para carregar apenas quando aberta ===
document.addEventListener('DOMContentLoaded', () => {
  const servicesTab = document.getElementById('services-tab');
  if (servicesTab) {
    servicesTab.addEventListener('shown.bs.tab', () => {
      setTimeout(() => loadServices(), 150);
    });
  }
});
