$arq_vhdx = $args[0].toupper() -replace '/','\'
$caminho = $args[1].toupper() -replace '/','\'
$montado = get-diskimage -ImagePath $arq_vhdx
if ($montado.attached)
{
	#O disco já estava montado.
	$diskImageItem = $montado
}
else
{
	$diskImageItem = Mount-DiskImage -ImagePath $arq_vhdx -PassThru | Get-DiskImage
}
$partitionItem = $diskImageItem | Get-Disk | Get-Partition | Where-Object -Property Type -EQ Basic | Select-Object -First 1
$partitionItemAccessPathItems = $partitionItem | Select-Object -ExpandProperty AccessPaths | Where-Object -FilterScript { $_ -notmatch '^\\\\\?' } | ForEach-Object -Process { $_ -replace '\\$', '' }
if ($partitionItemAccessPathItems.toupper() -contains $caminho)
{
	#O disco já estava montado na partição
}
else
{
	$partitionItem | Add-PartitionAccessPath -AccessPath $caminho
}
#Atualiza as unidades de disco no Powershell
Get-PSDrive | Out-Null
