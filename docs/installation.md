# Installation et configuration

[← Retour à l'accueil](../README.md) · [L'intégration](integration.md) · [Les cartes](cartes.md)

- [Prérequis](#prérequis)
- [Installer avec HACS](#installer-avec-hacs)
- [Ajouter l'intégration](#ajouter-lintégration)
- [Les options](#les-options)
- [Mettre à jour depuis la 1.2.8](#mettre-à-jour-depuis-la-128)
- [Dépannage](#dépannage)
- [Désinstaller](#désinstaller)

## Prérequis

- Un assistant d'énergie ecojoko<sup>©️</sup> installé et relié à votre compteur.
- Les identifiants de votre compte sur [service.ecojoko.com](https://service.ecojoko.com/).
- Home Assistant 2024.7 ou plus récent, et [HACS](https://hacs.xyz/).

## Installer avec HACS

1. Ajoutez le dépôt de l'intégration à HACS en cliquant sur ce bouton, puis sur **Ajouter** :

   [![Ouvrir HACS sur le dépôt Little Monkey](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmcruvellier&repository=little_monkey&category=integration)

2. Sur la page de Little Monkey dans HACS, cliquez sur **Télécharger**.
   Pour tester une version bêta, ouvrez le menu ⋮ › **Retélécharger**, activez **Afficher les versions bêta** et choisissez la version.
3. Redémarrez Home Assistant (Paramètres › Système › menu ⏻ › **Redémarrer Home Assistant**).

Les cartes du tableau de bord sont fournies par l'intégration elle-même : il n'y a ni ressource Lovelace ni dépôt HACS supplémentaire à installer.

## Ajouter l'intégration

Allez dans **Paramètres › Appareils et services**, cliquez sur **Ajouter une intégration** et cherchez **Little Monkey**. La configuration tient sur trois écrans.

### 1. Votre compte

<img src="images/ha/config-1-compte.png" alt="Écran du compte ecojoko" width="380">

| Champ | Description |
|---|---|
| Nom | Nom de l'appareil, qui préfixe le nom de tous les capteurs (« Ecojoko Consommation Temps Réel »…) |
| Nom d'utilisateur, Mot de passe | Vos identifiants ecojoko |

**Suivant** vérifie vos identifiants et lit le contrat d'électricité renseigné dans ecojoko. Un même compte ne peut être ajouté qu'une fois ; plusieurs comptes ecojoko peuvent coexister, chacun avec son entrée.

### 2. Les tranches tarifaires

<img src="images/ha/config-2-tranches.png" alt="Écran des tranches tarifaires" width="380">

L'écran affiche le contrat détecté et ses tranches (Heures Pleines et Creuses, Tempo Bleu, Blanc et Rouge, Semaine, Week-end, Jour Spécial…).

| Champ | Description |
|---|---|
| Capteurs totaux HC et HP | Crée « Consommation HC Réseau » et « Consommation HP Réseau », qui additionnent les tranches de chaque catégorie |
| Pour chaque tranche | Le nom de son capteur (prérempli) et le total dans lequel elle compte : Heures Creuses, Heures Pleines ou aucun |

Une tranche qu'ecojoko renomme garde son capteur et le nom que vous lui avez donné. Après un changement de contrat, ouvrez les options : elles reprennent cet écran avec les tranches du nouveau contrat, et une réparation le signale dans Home Assistant quand une tranche n'a pas de capteur.

### 3. Les autres capteurs et fonctions

<img src="images/ha/config-3-capteurs.png" alt="Écran des autres capteurs" width="380">

| Case | Par défaut | Effet |
|---|---|---|
| Capteur de production | décochée | Surplus de production injecté, pour un assistant ecojoko ancienne génération et des panneaux solaires |
| Capteurs d'humidité et de température | décochée | Température et humidité intérieures et extérieures de la sonde |
| Activité du compte | décochée | Économies, consommation et coût sur 7 jours, économies cumulées, puissances maximales ; faces 2 à 4 de la carte Little Monkey |
| Économies | décochée | Coûts et économies sur 12 mois, de la semaine, du mois et de l'année ; cartes Économies |
| Contrat | décochée | L'offre, ses tranches et le prix d'un kWh ; carte Contrat |
| Équipements pilotés | décochée | Le chauffe-eau (ou tout équipement piloté par ecojoko), ses capteurs et son pilotage ; carte Équipements |
| Analyse de la conso | décochée | La répartition par poste et les activations des appareils ; cartes Analyse de la conso et Activations |
| Mesures | décochée | La puissance du jour, l'énergie par tranche, la température et l'humidité ; carte Mesures |
| Fréquence de rafraîchissement | 5 s | Intervalle de lecture du temps réel, de 3 à 60 secondes |

Les six dernières cases, apparues avec la version 2.0.0, sont décochées par défaut : leurs capteurs ne sont créés, et leurs données lues chez ecojoko, que si elles sont cochées. Voir [les capteurs de chaque option](integration.md#les-capteurs).

> [!NOTE]
> Les noms des capteurs suivent la langue de votre instance Home Assistant : français, anglais ou portugais, anglais pour les autres langues.

## Les options

Le bouton **Configurer** de l'intégration reprend les trois écrans. Les nouveaux réglages ne sont enregistrés qu'après validation des identifiants par ecojoko, et l'intégration n'est rechargée qu'une fois.

- **Cocher une case** crée ses capteurs ; ceux qui existaient avant retrouvent leur historique.
- **Décocher une des six cases de la version 2.0.0** supprime ses capteurs, et les appareils des équipements pour « Équipements pilotés ». Les cartes qui en ont besoin affichent alors un message qui invite à la réactiver.
- **Décocher une autre case, ou changer de contrat**, laisse les capteurs concernés dans Home Assistant, à l'état « indisponible » : leur historique et leurs statistiques sont conservés. Les cartes n'en tiennent plus compte ; supprimez-les depuis leur page si vous n'en avez plus besoin.
- **Changer le nom** renomme l'appareil et le nom affiché des capteurs ; leurs identifiants et leur historique sont conservés.

## Mettre à jour depuis la 1.2.8

L'installation est convertie automatiquement au premier démarrage :

- les capteurs HC/HP et Tempo gardent leurs identifiants, leur historique et leurs statistiques ; l'option Tempo disparaît, un contrat Tempo n'étant plus qu'un contrat parmi d'autres ;
- pour un autre contrat (Week-end, Jour Spécial…), une réparation propose de créer les capteurs de ses tranches ;
- les nouvelles fonctions de la 2.0.0 sont décochées : ouvrez **Configurer** pour les activer.

> [!WARNING]
> Revenir ensuite à une version antérieure à la 1.2.8 demande de restaurer une sauvegarde ou de reconfigurer l'intégration.

## Dépannage

- **Les capteurs sont indisponibles** : ecojoko ne répond plus depuis plus de deux minutes. Une coupure plus courte conserve les dernières valeurs. L'état de chaque lecture est dans les journaux (Paramètres › Système › Journaux).
- **Les valeurs semblent figées** : ecojoko ne sert des données en direct que pendant dix minutes après la lecture de la liste de ses passerelles ; l'intégration la relit toutes les cinq minutes pour les maintenir vivantes. Un proxy ou un filtrage réseau qui met en cache les réponses d'ecojoko peut figer les données.
- **Une carte ne change pas après une mise à jour** : sur l'application mobile, videz le cache du frontend dans ses paramètres. Dans un navigateur, les cartes sont rechargées d'elles-mêmes.
- **Signaler un problème** : joignez les diagnostics (page de l'intégration › menu ⋮ › **Télécharger les diagnostics**). Vos identifiants, le nom de l'installation et les identifiants de vos équipements en sont retirés. Ouvrez une [issue](https://github.com/jmcruvellier/little_monkey/issues).

## Désinstaller

Supprimez l'entrée de l'intégration (page de l'intégration › menu ⋮ › **Supprimer**), puis Little Monkey dans HACS, et redémarrez Home Assistant.
