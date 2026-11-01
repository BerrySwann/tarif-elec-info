# TarifElecInfo

Petite intégration Home Assistant qui donne le prix du kWh du tarif réglementé (heures pleines / heures creuses) et **prévient avant chaque changement de tarif**.

Elle lit les prix TTC dans la grille publique du fournisseur, avec un repli sur le fichier ouvert officiel si la lecture du PDF n'est pas possible.

## Ce qu'elle fait

- capteurs : prix HP, prix HC, abonnement mensuel, source des prix, date du prochain changement, nombre de jours restants ;
- alerte **9 jours avant** chaque changement (1er février et 1er août), paramétrable ;
- alerte **la veille au soir** (20 h par défaut) : « à partir de ce soir minuit, le tarif change » ;
- notification toujours affichée dans Home Assistant, et en plus sur le téléphone choisi à l'installation ;
- relecture des prix toutes les 6 heures.

## Installation (HACS, dépôt personnalisé)

1. HACS, Dépôts personnalisés, ajouter `https://github.com/BerrySwann/tarif-elec-info` en catégorie « Intégration ».
2. Installer, puis redémarrer Home Assistant.
3. Paramètres, Appareils et services, Ajouter une intégration, « TarifElecInfo ».

## Installation manuelle

Copier le dossier `custom_components/tarifelecinfo` dans le dossier `config/custom_components/` de Home Assistant, puis redémarrer.

## Configuration

L'installation se fait en trois écrans :

1. **l'abonnement** : option tarifaire (heures pleines / creuses, base, tempo) et puissance souscrite. Obligatoire, les prix en dépendent ;
2. **les prix en vigueur** : l'intégration affiche ce qu'elle a lu à la source, avec la date ;
3. **le téléphone** : si un seul téléphone est enregistré il est présélectionné, si plusieurs il faut en choisir un, si aucun l'intégration continue mais prévient qu'il faudra en ajouter un.

Tout se règle ensuite dans Options (téléphone, nombre de jours avant l'annonce, heure du rappel).

## Limites connues

- La source officielle peut publier les nouveaux prix **plusieurs semaines après** l'entrée en vigueur : dans ce cas l'alerte le signale au lieu d'inventer des valeurs.
- La grille est un document de communication : si sa mise en page change, la lecture échoue proprement et l'intégration bascule sur le fichier ouvert (plus lent à être publié).
- Aucun lien avec EDF ni avec un fournisseur : l'intégration ne fait que lire des documents publics.
