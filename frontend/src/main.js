import './style.css'

const API_URL = 'http://localhost:8000'

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
