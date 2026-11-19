# Changelog

## 2.0.0b1

> [!WARNING]
> Version bêta : à installer pour tester, en activant l'affichage des versions bêta dans HACS. Signalez les problèmes dans les [issues](https://github.com/jmcruvellier/little_monkey/issues).

### Changements majeurs
- La configuration et les options tiennent sur trois écrans : identifiants, tranches tarifaires du contrat, autres capteurs. Les installations existantes sont converties automatiquement, sans perte d'historique
- Nouvelles options, chacune avec sa case dans le dernier écran des réglages, **décochée par défaut** : activité du compte, économies, contrat, équipements pilotés, analyse de la conso, mesures. Leurs capteurs ne sont créés, et leurs données lues chez ecojoko, que si la case est cochée ; les cartes qui en ont besoin invitent à l'activer
- Version minimale de Home Assistant : 2024.7.0

### Nouveautés et corrections
- Nouvelle carte « Little Monkey » pour les tableaux de bord, fournie par l'intégration elle-même : aucune ressource Lovelace à ajouter, elle est chargée automatiquement et suit toujours la version de l'intégration. Elle reprend le cadran du boîtier ecojoko : la puissance en temps réel sur un arc logarithmique, et dans le disque central la puissance, la puissance apparente (VA) quand elle est disponible et la courbe des dernières minutes. Avec l'option HC/HP ou Tempo, le disque prend la couleur de la période en cours, lue sur une entité de votre choix (couleur Tempo, heures creuses, période du compteur Linky...). Elle suit les thèmes clair et sombre de Home Assistant, en français et en anglais, et se configure avec un éditeur visuel qui choisit seul les capteurs de l'appareil Little Monkey
- Nouveau capteur « Période Tarifaire en Cours », créé avec l'option HC/HP ou Tempo : heures creuses ou pleines, et couleur du jour en Tempo. ecojoko ne donnant que l'énergie de chaque période, la période en cours est celle dont le compteur augmente : elle est connue avec quelques minutes de retard, et conservée quand la consommation est trop faible pour faire avancer un compteur. La carte l'utilise automatiquement pour colorer son disque
- Nouveaux capteurs tirés de l'activité du compte ecojoko : Économies sur 7 Jours (en % par rapport à la consommation de référence, la donnée de l'aiguille du bas du cadran ecojoko), Consommation (avec celle de chaque jour en attribut) et Coût sur 7 Jours, Économies Cumulées, Puissance Max du mois, de l'année et depuis le début. ecojoko calculant lentement ces valeurs, elles sont lues à part, toutes les dix minutes : une lenteur ou une panne de cette API ne touche jamais les capteurs temps réel, et leurs dernières valeurs sont conservées pendant une heure. Sur la carte, l'aiguille du bas indique désormais les économies sur 7 jours, et le disque central gagne, comme celui d'ecojoko, trois faces que l'on fait défiler en glissant ou avec les points : économies sur 7 jours, coût et consommation sur 7 jours avec l'histogramme des jours, puissance maximale. Il revient seul sur la puissance temps réel après 30 secondes, et titre « INJECTION RÉSEAU » pendant l'injection d'un surplus. Le cadran prend du relief et un fond tiré du thème, réglables dans l'éditeur (relief, fond du cadran : par défaut, transparent, palette de Home Assistant ou couleur libre)
- Nouveaux capteurs des économies, ceux de l'onglet « Économies » d'ecojoko : sur les 12 derniers mois, le coût de la consommation, celui de la consommation de référence et les économies ; pour la semaine, le mois et l'année en cours, les économies en euros avec leur détail jour par jour, semaine par semaine ou mois par mois en attribut. Ils sont lus à part, toutes les demi-heures, comme l'activité du compte : une panne de ces API ne touche jamais les autres capteurs
- Nouveau service « Lire les économies » (`little_monkey.get_savings`) : les économies de n'importe quelle semaine, mois ou année, avec leur détail, pour remonter dans le temps depuis un script, une automatisation ou la carte « Détail des économies »
- Nouvelle carte « Résumé des économies », chargée automatiquement comme celle du cadran : la consommation en cours, la consommation de référence et les économies des 12 derniers mois en trois barres, comme dans l'application ecojoko, en euros ou en kWh
- Nouvelle carte « Détail des économies » : les économies de la semaine, du mois ou de l'année en barres, jour par jour, semaine par semaine ou mois par mois, comme dans l'application ecojoko. On remonte dans le temps avec les flèches ou en glissant le doigt, et toucher une barre affiche son détail
- Nouveaux services de l'analyse de la consommation, ceux de la page « Analyse de votre conso » d'ecojoko : répartition de la consommation d'une semaine ou d'un mois par poste (`little_monkey.get_consumption_analysis`), historique d'un poste semaine par semaine (`little_monkey.get_category_history`) et activations des appareils (`little_monkey.get_activations`)
- Nouvelle carte « Analyse de la conso » : la consommation d'une semaine ou d'un mois par poste (talon, éclairage, froid, cuisson…), l'anneau à côté des principaux postes, avec le coût, la part et la tendance de chacun, comme dans l'application ecojoko. On remonte dans le temps avec les flèches ou en glissant le doigt, et toucher un poste affiche son historique semaine par semaine sur l'année
- Nouvelle carte « Mesures », celle de la page « Mesures » d'ecojoko : la courbe de puissance du jour colorée par tranche tarifaire au-dessus du talon, et les jours ou les mois d'une semaine, d'un mois ou d'une année en barres empilées par tranche, en kWh ou en euros, avec la production injectée ; et la température et l'humidité intérieures et extérieures en courbes, tirées des statistiques des capteurs de Home Assistant quand ils existent, d'ecojoko sinon
- Nouveau service « Lire les mesures » (`little_monkey.get_measures`), celui de la page « Mesures » d'ecojoko : la puissance d'un jour avec sa tranche tarifaire, l'énergie et le coût des jours ou des mois par tranche, la température et l'humidité intérieures et extérieures
- Nouvelle carte « Activations des appareils » : les démarrages d'appareils détectés par ecojoko, en une frise de 24 heures par jour où chaque activation est une impulsion à son heure ; toucher une impulsion affiche ses heures, sa durée, son énergie et sa puissance moyenne (affichage en liste possible)
- Nouveau capteur « Contrat » (diagnostic) : le nom de l'offre lue chez ecojoko, avec en attribut le fournisseur, la puissance souscrite, l'abonnement, la date de début, les plages d'heures creuses et les tranches tarifaires configurées. Les diagnostics continuent d'afficher le contrat sans son prix
- Nouvelle carte « Contrat » : le fournisseur et l'offre, un cadran des 24 heures avec les heures creuses, la période en cours et le prochain changement (aux couleurs du jour avec Tempo), les tranches tarifaires avec le prix d'un kWh et la tranche en cours en gras, et l'abonnement. Le prix est celui d'ecojoko quand il le connaît (avec un chauffe-eau piloté, et selon l'offre), estimé d'après ses coûts quotidiens sinon ; le capteur Contrat le donne aussi en attribut
- Nouveaux capteurs des équipements pilotés par ecojoko (chauffe-eau, prise pilotée…) : chacun devient un appareil de Home Assistant, rattaché à l'appareil Little Monkey, avec son mode (Automatique, Forcé, Absence), sa puissance, et sa consommation et son coût du jour. Ils sont lus toutes les deux minutes, à part des autres capteurs. Les équipements d'un type inconnu sont pris en charge d'après les commandes qu'ecojoko leur reconnaît
- Nouveaux capteurs de diagnostic des équipements de l'installation (capteur d'électricité, sonde, chauffe-eau…) : connexion à l'assistant, force de la connexion, connexion au WiFi, batterie, tension des piles et état de l'installation du capteur d'électricité (« Bien placé »), quand ecojoko les donne. La batterie est affichée comme dans l'application ecojoko, par paliers de 20 %. Ils sont sur l'appareil d'un équipement piloté, et sur l'appareil Little Monkey pour les autres, qui n'ont pas d'appareil à eux
- Pilotage des équipements, comme dans l'application ecojoko : une liste « Pilotage » sur chaque équipement piloté (Automatique, Forcé pendant une heure, Absence jusqu'à minuit, ou Allumé et Éteint pour un équipement sans mode forcé) et un service « Piloter un équipement » (`little_monkey.set_equipment_mode`) qui choisit la durée du forçage ou de l'absence, ou la fin de l'absence
- Nouvelle carte « Équipements », celle de l'écran « Équipements » d'ecojoko : pour chaque équipement piloté, son mode, sa puissance et les boutons d'ecojoko (Forcé 1 à 4 heures ou une autre durée, Absence jusqu'à une date, Automatique, ou Allumer et Éteindre), et ouvert, sa consommation, son coût et la frise de sa journée ; les autres équipements listés avec leurs mesures (température et humidité de la sonde, puissance du capteur d'électricité) et, sous leur nom, l'état de l'installation, la batterie, la tension des piles et le signal. Avec plusieurs équipements pilotés, un seul bloc est ouvert à la fois. Toucher une valeur ouvre ses détails, comme dans les autres cartes ; le chauffe-eau gagne pour cela les capteurs Tension et Puissance Max Mesurée. Ses boutons et ses mesures viennent de ce qu'ecojoko propose pour chaque équipement, quel que soit son type
- Nouveau service « Lire les équipements » (`little_monkey.get_equipments`) : les équipements de l'installation, leur état, et les mesures du jour des équipements pilotés
- Prise en charge de tous les contrats d'électricité renseignés dans ecojoko, et plus seulement EDF Tarif Bleu et Tempo ([#108](https://github.com/jmcruvellier/little_monkey/issues/108), [#109](https://github.com/jmcruvellier/little_monkey/issues/109), [#74](https://github.com/jmcruvellier/little_monkey/issues/74)) : la configuration et les options tiennent désormais sur trois écrans. Le premier vérifie vos identifiants et lit votre contrat ; le deuxième affiche ses tranches tarifaires (Heures Pleines/Creuses, Tempo, Semaine, Week-end, Jour Spécial…) et vous laisse choisir pour chacune le nom de son capteur et le total, HC ou HP, dans lequel elle compte ; le troisième reprend les autres capteurs. La case Tempo disparaît : un contrat Tempo n'est plus qu'un contrat parmi d'autres. Une tranche qu'ecojoko renomme garde son capteur et son nom
- Capteurs HC et HP corrects pour tous les contrats : ils additionnent désormais toutes les tranches de leur catégorie, au lieu de ne garder que la dernière lue. Les contrats Zen Week-End Plus, un jour Tempo qui change de couleur ou l'option HC/HP seule sur un contrat Tempo donnaient des valeurs fausses ; le samedi d'un contrat HC + Week-end, HC et HP valent désormais 0 au lieu de garder la valeur du vendredi
- Les installations existantes sont converties automatiquement : les capteurs HC/HP et Tempo gardent leurs identifiants, leur historique et leurs statistiques. Une réparation apparaît dans Home Assistant quand ecojoko indique des tranches sans capteur (changement de contrat, contrat Week-end ou Jour Spécial d'une installation convertie) : la valider crée leurs capteurs
- Le capteur « Période Tarifaire en Cours » indique en attribut la tranche en cours (par exemple « HP Jour Spécial » ou « Heures Weekend »), déduite du compteur qui augmente
- Les diagnostics indiquent le contrat lu chez ecojoko (sans prix) et les tranches tarifaires rencontrées
- Documentation entièrement revue, avec des captures d'écran : le README présente l'intégration et les cartes, et trois guides détaillent l'[installation](docs/installation.md), [l'intégration](docs/integration.md) et [les cartes](docs/cartes.md). Le lien d'aide de chaque carte mène à sa section
- Version minimale de Home Assistant relevée à 2024.7.0 (au lieu de 2024.6.0) : la carte est servie avec la fonction de Home Assistant prévue à cet effet depuis cette version, l'ancienne étant retirée de Home Assistant 2025.7

## 1.2.8
- Nouveau capteur « Puissance Apparente » (VA), créé quand ecojoko fournit cette mesure du compteur Linky ([#123](https://github.com/jmcruvellier/little_monkey/issues/123))
- Correction des données de consommation erronées (Consommation Réseau, HC/HP, Tempo, surplus de production) : l'API ecojoko renvoyait des valeurs dégradées au User-Agent par défaut de Home Assistant, l'intégration envoie désormais son propre User-Agent
- Les capteurs passent à l'état « indisponible » quand l'API ecojoko ne répond plus depuis deux minutes, au lieu de rester figés sur leur dernière valeur ; une coupure plus brève (délai dépassé, résolution DNS) conserve les dernières valeurs. Les erreurs sont désormais journalisées, celles des statistiques seulement si elles se répètent
- Données maintenues vivantes : ecojoko n'alimente ses APIs en direct que pendant dix minutes après la lecture de la liste des passerelles, puis sert des données périmées (temps réel figé, énergies en retard) sans aucune erreur. L'intégration relit désormais cette liste toutes les cinq minutes
- Demande de ré-authentification quand ecojoko refuse le mot de passe, et messages d'erreur précis (identifiants incorrects, connexion impossible) lors de la configuration
- Options : les nouveaux paramètres ne sont enregistrés qu'après validation par ecojoko, et l'intégration n'est rechargée qu'une seule fois
- Température et humidité : rafraîchissement désormais assuré quelle que soit la fréquence choisie (elles n'étaient plus mises à jour à partir de 15 secondes pour l'humidité et de 30 secondes pour la température), et plus aucun appel à ces APIs quand l'option est décochée
- Les données de consommation ne sont plus figées pendant une heure lors du passage à l'heure d'hiver
- Capteurs conformes aux pratiques de Home Assistant (valeur et unité natives) : la conversion d'unité fonctionne désormais, par exemple pour un système configuré en °F
- Les noms des capteurs utilisent désormais les traductions natives de Home Assistant : ils suivent la langue de l'instance (français, anglais, portugais) et l'option de langue de l'intégration disparaît. Les identifiants d'entité, l'historique et les statistiques ne changent pas ; seul le nom affiché perd son tiret (« Ecojoko Consommation Temps Réel » au lieu de « Ecojoko - Consommation Temps Réel »), sauf si vous l'avez personnalisé
- Changer le nom dans les options ne recrée plus les capteurs : entités et appareil sont désormais identifiés par l'entrée de configuration et non par le nom. Les installations existantes sont migrées automatiquement au premier démarrage, en conservant identifiants d'entité, historique et statistiques. Attention : après cette migration, revenir à une version antérieure à la 1.2.8 demande de restaurer une sauvegarde ou de reconfigurer l'intégration
- Un ancien appareil laissé par un renommage fait avec une version précédente peut maintenant être supprimé depuis sa page ([#126](https://github.com/jmcruvellier/little_monkey/issues/126)) ; l'appareil actif reste protégé
- Un même compte ecojoko ne peut plus être ajouté deux fois
- Le nom est désormais obligatoire à l'installation et dans les options
- Une erreur HTTP d'ecojoko (4xx, 5xx) est désormais traitée comme une erreur, y compris à la connexion, au lieu d'être prise pour une réponse valide ; le délai d'attente couvre toute la réponse et les connexions sont toujours libérées
- Ajout des diagnostics de l'intégration (téléchargeables depuis la page de l'appareil ou de l'intégration), identifiants ecojoko et nom de l'installation masqués, pour faciliter les rapports de bug ; ils indiquent aussi le code et les en-têtes de la dernière réponse de chaque API d'ecojoko
- Version minimale de Home Assistant relevée à 2024.6.0 (au lieu de 2023.9.0) : l'intégration s'appuie désormais sur des fonctions de Home Assistant apparues dans cette version, et elle est testée automatiquement sur cette version comme sur la plus récente
- Les capteurs d'énergie ne baissent plus en cours de journée : quand ecojoko corrige une valeur à la baisse, la dernière valeur est conservée jusqu'à ce que la mesure la rattrape. Home Assistant prenait ces baisses pour une remise à zéro du compteur et pouvait compter deux fois l'énergie dans le tableau Énergie ; l'avertissement « state is not strictly increasing » disparaît
- Au changement de jour, un capteur d'énergie dont ecojoko ne donne pas encore la valeur passe à « inconnu » au lieu de garder la valeur de la veille
- La connexion à ecojoko envoie désormais les identifiants par une requête POST, au lieu d'une requête GET avec corps
- Chaque compte ecojoko utilise sa propre session HTTP, au lieu de la session partagée de Home Assistant : ses cookies ne sont plus mélangés avec ceux d'un autre compte
- Les valeurs reçues d'ecojoko sont arrondies à deux décimales : une température comme 19.900000000000002 devient 19.9
- Suppression de deux dépendances non déclarées (`async_timeout`, `pytz`) au profit de la bibliothèque standard de Python

## 1.2.7
- Correction du bug [#118](https://github.com/jmcruvellier/little_monkey/issues/118) : Entités non affichées dans l'appareil Ecojoko

## 1.2.6
- Correction du bug [#116](https://github.com/jmcruvellier/little_monkey/issues/116) : Problème de reporting sur la page energie

## 1.2.5
- Correction du bug [#110](https://github.com/jmcruvellier/little_monkey/issues/110) : Surplus de production attendu en positif et plus en négatif
- Fix URL dans le json des traductions (nouvelle règle de validation de la qualité du code)

## 1.2.4
- Correction du bug [#101](https://github.com/jmcruvellier/little_monkey/issues/101)

## 1.2.3
- Correction du bug [#93](https://github.com/jmcruvellier/little_monkey/issues/93)
- Ajout du portugais à la liste des langues disponibles [#80](https://github.com/jmcruvellier/little_monkey/pull/80) [#88](https://github.com/jmcruvellier/little_monkey/pull/88) [#89](https://github.com/jmcruvellier/little_monkey/pull/89)

## 1.2.2
- Correction du bug [#74](https://github.com/jmcruvellier/little_monkey/issues/74)

## 1.2.1
- Correction du bug [#78](https://github.com/jmcruvellier/little_monkey/issues/78)

## 1.2.0
- Optimisation majeure du code et des performances
- Suppression des capteurs introduits en v1.1.0, basés sur les APIs Measurements d'ecojoko
- Correction du bug [#58](https://github.com/jmcruvellier/little_monkey/issues/58)

## 1.1.0
- Nouveaux capteurs basés sur les APIs Measurements d'ecojoko
- Améliorations de performance et corrections de bugs mineurs
- Correction du bug [#58](https://github.com/jmcruvellier/little_monkey/issues/58)
- Correction du bug [#71](https://github.com/jmcruvellier/little_monkey/issues/71)

## 1.0.1

- Correction du bug [#67](https://github.com/jmcruvellier/little_monkey/issues/67)
- Correction du bug [#68](https://github.com/jmcruvellier/little_monkey/issues/68)

## 1.0.0

- Pays HACS, par @jmcruvellier dans https://github.com/jmcruvellier/little_monkey/pull/66
- Prêt pour la publication dans le Home Assistant Community Store https://github.com/hacs/default/pull/2162

## 0.1.3

- Correction du bug [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.2

- Correction du bug [#63](https://github.com/jmcruvellier/little_monkey/issues/63)

## 0.1.1

- Correction du bug [#59](https://github.com/jmcruvellier/little_monkey/issues/59)

## 0.1.0

- Version Beta

## 0.0.1

- Version Alpha
