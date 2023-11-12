# Installation & Configuration

## Installation pas à pas

1. Cliquer sur le lien d'installation, saisir l'adresse de votre instance Home Assistant, puis cliquer sur "Open Link":
![Etape 1](/custom_components/little_monkey/res/install_step_01.png)

1. Cliquer sur le bouton "Ajouter":
![Etape 2](/custom_components/little_monkey/res/install_step_02.png)

1. Cliquer sur le bouton "Télécharger" en bas de la page:
![Etape 3](/custom_components/little_monkey/res/install_step_03.png)

1. Cliquer sur le bouton "Télécharger":
![Etape 4](/custom_components/little_monkey/res/install_step_04.png)

1. L'intégration "Little Monkey" apparaît dans le Ouvrir Home Assistant Community Store (HACS):
![Etape 5](/custom_components/little_monkey/res/install_step_05.png)

1. Il est nécessaire de redémarrer Home Assistant pour que l'intégration fonctionne:
  - Aller dans "Paramètres":
  ![Etape 6](/custom_components/little_monkey/res/install_step_06.png)
  - Cliquer sur le message "Restart required" pui sur le bouton "Valider":
  ![Etape 7](/custom_components/little_monkey/res/install_step_07.png)

1. Le redémarrage est lancé:
  ![Etape 8](/custom_components/little_monkey/res/install_step_08.png)


## Configuration

Une fois Home Assistant redémarré, l'intégration peut maintenant être configurée.

1.  Aller dans "Paramètres", "Appareils et Services" et dans l'onglet "Intégrations" cliquer sur le bouton "Ajouter une Intégration". Rechercher "Little Monkey" et cliquer dessus:
![Etape 9](/custom_components/little_monkey/res/install_step_09.png)

1. Saisir et Sélectionner les options de configurations:
  - Nom: nom qui sera utilisé pour préfixer les noms de tous les capteurs
  - Nom d'utilisateur et Mot de passe: vos identifiants ecojoko<sup>©️</sup>
  - Capteurs HP/HC: à ne sélectionner que si vous avez renseigné un tarif d'électricité avec des Heures Creuses dans ecojoko<sup>©️</sup>
  - Capteurs Tempo Bleu/Blanc/Rouge: à ne sélectionner que si vous avez renseigné un tarif d'électricité Tempo
  - Capteurs d'humidité et de température: à ne sélectionner que si vous désirez remonter ces données depuis votre ecojoko<sup>©️</sup>
  - Capteur de production: à ne sélectionner que si vous êtes producteur d'énergie solaire et que avez un capteur ecojoko<sup>©️</sup> ancienne génération
  - Fréquence de raffraichissement des données (en secondes): le minimum autorisé est de 3 secondes (afin de ne pas surcharger les serveurs d'ecojoko<sup>©️</sup>), et le maximum est de 60 secondes
  - Choix de la langue: français par défaut, possibilité de passer en anglais
> [!IMPORTANT]
> Un changement de nom ou de langue après la première configuration nécessitera un rechargement de l'intégration et entrainera un renommage des capteurs
![Etape 1](/custom_components/little_monkey/res/config_step_01.png)

1. La configuration est terminée:
![Etape 2](/custom_components/little_monkey/res/config_step_02.png)

1. Voici un exemple de tous les capteurs créés:
![Etape 3](/custom_components/little_monkey/res/config_step_03.png)
