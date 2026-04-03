// Global variables
var currentStudyPlan = null;
var taskCompletion = {};
var totalTasks = 0;
var currentLanguage = 'en';

// Click-to-play YouTube embed - replaces thumbnail with iframe
function playYouTubeVideo(card, videoId) {
    if (!videoId || videoId.length !== 11) return;
    
    var thumbnailContainer = card.querySelector('.youtube-card-thumbnail');
    if (!thumbnailContainer) return;
    
    // Check if already playing
    if (card.classList.contains('playing')) {
        return;
    }
    
    card.classList.add('playing');
    
    // Create iframe embed
    var iframe = document.createElement('iframe');
    iframe.setAttribute('width', '100%');
    iframe.setAttribute('height', '100%');
    iframe.setAttribute('src', 'https://www.youtube.com/embed/' + videoId + '?autoplay=1&rel=0');
    iframe.setAttribute('frameborder', '0');
    iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture');
    iframe.setAttribute('allowfullscreen', 'true');
    iframe.setAttribute('title', 'YouTube video player');
    
    // Replace thumbnail with iframe
    thumbnailContainer.innerHTML = '';
    thumbnailContainer.appendChild(iframe);
}

// Close embedded video and show thumbnail again
function closeYouTubeVideo(card) {
    var thumbnailContainer = card.querySelector('.youtube-card-thumbnail');
    var videoId = card.getAttribute('data-video-id');
    
    if (thumbnailContainer && videoId) {
        card.classList.remove('playing');
        
        // Restore thumbnail
        thumbnailContainer.innerHTML = '<img src="https://img.youtube.com/vi/' + videoId + '/hqdefault.jpg" alt="Video">' +
            '<div class="play-overlay"><i class="fas fa-play-circle"></i></div>';
    }
}

// Translations object
var translations = {
    en: {
        // Header
        yourStudyDashboard: 'Your Study Dashboard',
        trackYourStudy: 'Track your personalized study adventure',
        theme: 'Theme',
        copy: 'Copy',
        download: 'Download',
        share: 'Share',
        
        // Sidebar
        yourDetails: 'Your Details',
        yourName: 'Your Name',
        enterYourName: 'Enter your name',
        subjectsTopics: 'Subjects & Topics',
        enterSubjectsTopics: 'Enter subjects and topics',
        durationDays: 'Duration (in days)',
        howManyDaysStudy: 'How many days do you want to study?',
        dailyStudyHours: 'Daily Study Hours',
        howManyHoursDay: 'How many hours can you study per day?',
        generateMyPlan: 'Generate My Plan',
        madeWithForStudents: 'Made with <i class="fas fa-heart"></i> for students',
        
        // Welcome card
        readyToStudy: 'Ready to Study Smarter?',
        welcomeDescription: 'Tell us about your subjects and duration, and we\'ll create a personalized roadmap to help you learn!',
        dayWiseSchedule: 'Day-wise Schedule',
        topicBreakdown: 'Topic Breakdown',
        freeResources: 'Free Resources',
        
        // Loader
        craftingStudyPlan: 'Crafting your perfect study plan...',
        
        // Sections
        keyConcepts: 'Key Concepts',
        explanation: 'Explanation',
        studyPlan: 'Study Plan',
        youtubeTutorials: 'YouTube Tutorials',
        
        // Mark complete
        markAsComplete: 'Mark as Complete',
        completed: 'Completed',
        
        // Messages
        copiedToClipboard: 'Copied to clipboard!',
        failedToCopy: 'Failed to copy',
        studyPlanReady: 'Study plan ready!',
        failedToGenerate: 'Failed to generate',
        pleaseFillAllFields: 'Please fill all fields',
        error: 'Error',
        taskMarkedComplete: 'Task marked as complete!',
        taskUnmarked: 'Task unmarked',
        
        // Share/Download
        studyPlanDownloaded: 'Study plan downloaded as PDF!',
        downloadedAsText: 'Downloaded as text file',
        sharedSuccessfully: 'Shared successfully!',
        shareCancelled: 'Share cancelled',
        copiedForSharing: 'Copied to clipboard for sharing!',
        
        // Celebration
        milestoneAchieved: 'Milestone Achieved!',
        completedTasks: 'You have completed all your tasks! Keep going!',
        
        // No resources
        noTutorialsFound: 'No tutorials found',
        noExplanationAvailable: 'No explanation available',
        
        // Student info
        welcomeBack: 'Welcome back,',
        subjects: 'Subjects',
        duration: 'Duration',
        dailyHours: 'Daily Hours',
        days: 'days',
        hours: 'hours',
        
        // Day labels
        day: 'Day',
        
        // PDF Modal
        pdfNotSupported: 'PDF generation not supported in this browser.',
        downloadTextInstead: 'Would you like to download as a text file instead?',
        yes: 'Yes',
        no: 'No',
        generatingPdf: 'Generating PDF...',
        
        // AI Study Planner
        aiStudyPlanner: 'AI Study Planner',
        smartLearning: 'Smart Learning'
    },
    hi: {
        yourStudyDashboard: 'आपका अध्ययन डैशबोर्ड',
        trackYourStudy: 'अपनी व्यक्तिगत अध्ययन यात्रा को ट्रैक करें',
        theme: 'थीम',
        copy: 'कॉपी करें',
        download: 'डाउनलोड',
        share: 'शेयर करें',
        
        yourDetails: 'आपका विवरण',
        yourName: 'आपका नाम',
        enterYourName: 'अपना नाम दर्ज करें',
        subjectsTopics: 'विषय और टॉपिक',
        enterSubjectsTopics: 'विषय और टॉपिक दर्ज करें',
        durationDays: 'अवधि (दिनों में)',
        howManyDaysStudy: 'आप कितने दिन पढ़ना चाहते हैं?',
        dailyStudyHours: 'दैनिक अध्ययन घंटे',
        howManyHoursDay: 'आप प्रतिदिन कितने घंटे पढ़ सकते हैं?',
        generateMyPlan: 'मेरी योजना बनाएं',
        madeWithForStudents: 'छात्रों के लिए <i class="fas fa-heart"></i> के साथ बनाया गया',
        
        readyToStudy: 'स्मार्ट पढ़ाई के लिए तैयार?',
        welcomeDescription: 'अपने विषयों और अवधि के बारे में बताएं, और हम आपकी सीखने में मदद के लिए एक व्यक्तिगत रोडमैप बनाएंगे!',
        dayWiseSchedule: 'दिन-वार शेड्यूल',
        topicBreakdown: 'टॉपिक विवरण',
        freeResources: 'मुफ्त संसाधन',
        
        craftingStudyPlan: 'आपकी परफेक्ट स्टडी प्लान बना रहे हैं...',
        
        keyConcepts: 'मुख्य अवधारणाएं',
        explanation: 'स्पष्टीकरण',
        studyPlan: 'अध्ययन योजना',
        youtubeTutorials: 'YouTube ट्यूटोरियल',
        
        markAsComplete: 'पूर्ण के रूप में चिह्नित करें',
        completed: 'पूर्ण',
        
        copiedToClipboard: 'क्लिपबोर्ड पर कॉपी किया गया!',
        failedToCopy: 'कॉपी करने में विफल',
        studyPlanReady: 'स्टडी प्लान तैयार!',
        failedToGenerate: 'बनाने में विफल',
        pleaseFillAllFields: 'कृपया सभी फ़ील्ड भरें',
        error: 'त्रुटि',
        taskMarkedComplete: 'टास्क पूर्ण चिह्नित!',
        taskUnmarked: 'टास्क अनचिह्नित',
        
        studyPlanDownloaded: 'स्टडी प्लान PDF के रूप में डाउनलोड हुआ!',
        downloadedAsText: 'टेक्स्ट फ़ाइल के रूप में डाउनलोड किया गया',
        sharedSuccessfully: 'सफलतापूर्वक शेयर किया गया!',
        shareCancelled: 'शेयर रद्द किया गया',
        copiedForSharing: 'शेयर करने के लिए क्लिपबोर्ड पर कॉपी किया गया!',
        
        milestoneAchieved: 'माइलस्टोन हासिल!',
        completedTasks: 'आपने सभी टास्क पूरे कर लिए! जारी रखें!',
        
        noTutorialsFound: 'कोई ट्यूटोरियल नहीं मिला',
        noExplanationAvailable: 'कोई स्पष्टीकरण उपलब्ध नहीं',
        
        welcomeBack: 'वापसी पर स्वागत है,',
        subjects: 'विषय',
        duration: 'अवधि',
        dailyHours: 'दैनिक घंटे',
        days: 'दिन',
        hours: 'घंटे',
        
        day: 'दिन',
        
        pdfNotSupported: 'इस ब्राउज़र में PDF जनरेशन समर्थित नहीं है।',
        downloadTextInstead: 'क्या आप इसे टेक्स्ट फ़ाइल के रूप में डाउनलोड करना चाहेंगे?',
        yes: 'हाँ',
        no: 'नहीं',
        generatingPdf: 'PDF बना रहे हैं...',
        
        aiStudyPlanner: 'AI स्टडी प्लानर',
        smartLearning: 'स्मार्ट लर्निंग'
    },
    es: {
        yourStudyDashboard: 'Tu Panel de Estudio',
        trackYourStudy: 'Rastrea tu aventura de aprendizaje personalizada',
        theme: 'Tema',
        copy: 'Copiar',
        download: 'Descargar',
        share: 'Compartir',
        
        yourDetails: 'Tus Detalles',
        yourName: 'Tu Nombre',
        enterYourName: 'Ingresa tu nombre',
        subjectsTopics: 'Materias y Temas',
        enterSubjectsTopics: 'Ingresa materias y temas',
        durationDays: 'Duración (en días)',
        howManyDaysStudy: '¿Cuántos días quieres estudiar?',
        dailyStudyHours: 'Horas de Estudio Diarias',
        howManyHoursDay: '¿Cuántas horas puedes estudiar por día?',
        generateMyPlan: 'Generar Mi Plan',
        madeWithForStudents: 'Hecho con <i class="fas fa-heart"></i> para estudiantes',
        
        readyToStudy: '¿Listo para Estudiar Más Inteligente?',
        welcomeDescription: '¡Cuéntanos sobre tus materias y duración, y crearemos una hoja de ruta personalizada para ayudarte a aprender!',
        dayWiseSchedule: 'Horario por Día',
        topicBreakdown: 'Desglose de Temas',
        freeResources: 'Recursos Gratuitos',
        
        craftingStudyPlan: 'Creando tu plan de estudio perfecto...',
        
        keyConcepts: 'Conceptos Clave',
        explanation: 'Explicación',
        studyPlan: 'Plan de Estudio',
        youtubeTutorials: 'Tutoriales de YouTube',
        
        markAsComplete: 'Marcar como Completo',
        completed: 'Completado',
        
        copiedToClipboard: '¡Copiado al portapapeles!',
        failedToCopy: 'Error al copiar',
        studyPlanReady: '¡Plan de estudio listo!',
        failedToGenerate: 'Error al generar',
        pleaseFillAllFields: 'Por favor completa todos los campos',
        error: 'Error',
        taskMarkedComplete: '¡Tarea marcada como completa!',
        taskUnmarked: 'Tarea desmarcada',
        
        studyPlanDownloaded: '¡Plan de estudio descargado como PDF!',
        downloadedAsText: 'Descargado como archivo de texto',
        sharedSuccessfully: '¡Compartido exitosamente!',
        shareCancelled: 'Compartir cancelado',
        copiedForSharing: '¡Copiado al portapapeles para compartir!',
        
        milestoneAchieved: '¡Hito Alcanzado!',
        completedTasks: '¡Has completado todas tus tareas! ¡Sigue así!',
        
        noTutorialsFound: 'No se encontraron tutoriales',
        noExplanationAvailable: 'No hay explicación disponible',
        
        welcomeBack: 'Bienvenido de nuevo,',
        subjects: 'Materias',
        duration: 'Duración',
        dailyHours: 'Horas Diarias',
        days: 'días',
        hours: 'horas',
        
        day: 'Día',
        
        pdfNotSupported: 'La generación de PDF no es compatible con este navegador.',
        downloadTextInstead: '¿Te gustaría descargar como archivo de texto?',
        yes: 'Sí',
        no: 'No',
        generatingPdf: 'Generando PDF...',
        
        aiStudyPlanner: 'Planificador de Estudio IA',
        smartLearning: 'Aprendizaje Inteligente'
    },
    fr: {
        yourStudyDashboard: 'Votre Tableau de Bord',
        trackYourStudy: 'Suivez votre aventure d\'apprentissage personnalisée',
        theme: 'Thème',
        copy: 'Copier',
        download: 'Télécharger',
        share: 'Partager',
        
        yourDetails: 'Vos Détails',
        yourName: 'Votre Nom',
        enterYourName: 'Entrez votre nom',
        subjectsTopics: 'Sujets et Thèmes',
        enterSubjectsTopics: 'Entrez les sujets et thèmes',
        durationDays: 'Durée (en jours)',
        howManyDaysStudy: 'Combien de jours voulez-vous étudier?',
        dailyStudyHours: 'Heures d\'Étude Quotidiennes',
        howManyHoursDay: 'Combien d\'heures pouvez-vous étudier par jour?',
        generateMyPlan: 'Générer Mon Plan',
        madeWithForStudents: 'Fait avec <i class="fas fa-heart"></i> pour les étudiants',
        
        readyToStudy: 'Prêt à Étudier Plus Intelligemment?',
        welcomeDescription: 'Parlez-nous de vos sujets et de votre durée, et nous créerons une feuille de route personnalisée pour vous aider à apprendre!',
        dayWiseSchedule: 'Programme Quotidien',
        topicBreakdown: 'Détail des Thèmes',
        freeResources: 'Ressources Gratuites',
        
        craftingStudyPlan: 'Création de votre plan d\'étude parfait...',
        
        keyConcepts: 'Concepts Clés',
        explanation: 'Explication',
        studyPlan: 'Plan d\'Étude',
        youtubeTutorials: 'Tutoriels YouTube',
        
        markAsComplete: 'Marquer comme Terminé',
        completed: 'Terminé',
        
        copiedToClipboard: 'Copié dans le presse-papiers!',
        failedToCopy: 'Échec de la copie',
        studyPlanReady: 'Plan d\'étude prêt!',
        failedToGenerate: 'Échec de la génération',
        pleaseFillAllFields: 'Veuillez remplir tous les champs',
        error: 'Erreur',
        taskMarkedComplete: 'Tâche marquée comme terminée!',
        taskUnmarked: 'Tâche non marquée',
        
        studyPlanDownloaded: 'Plan d\'étude téléchargé en PDF!',
        downloadedAsText: 'Téléchargé en fichier texte',
        sharedSuccessfully: 'Partagé avec succès!',
        shareCancelled: 'Partage annulé',
        copiedForSharing: 'Copié dans le presse-papiers pour le partage!',
        
        milestoneAchieved: 'Jalon Atteint!',
        completedTasks: 'Vous avez complété toutes vos tâches! Continuez!',
        
        noTutorialsFound: 'Aucun tutoriel trouvé',
        noExplanationAvailable: 'Aucune explication disponible',
        
        welcomeBack: 'Bon retour,',
        subjects: 'Sujets',
        duration: 'Durée',
        dailyHours: 'Heures Quotidiennes',
        days: 'jours',
        hours: 'heures',
        
        day: 'Jour',
        
        pdfNotSupported: 'La génération PDF n\'est pas prise en charge par ce navigateur.',
        downloadTextInstead: 'Voulez-vous télécharger en fichier texte à la place?',
        yes: 'Oui',
        no: 'Non',
        generatingPdf: 'Génération du PDF...',
        
        aiStudyPlanner: 'Planificateur d\'Étude IA',
        smartLearning: 'Apprentissage Intelligent'
    },
    de: {
        yourStudyDashboard: 'Ihr Lern-Dashboard',
        trackYourStudy: 'Verfolgen Sie Ihre personalisierte Lernreise',
        theme: 'Design',
        copy: 'Kopieren',
        download: 'Herunterladen',
        share: 'Teilen',
        
        yourDetails: 'Ihre Details',
        yourName: 'Ihr Name',
        enterYourName: 'Geben Sie Ihren Namen ein',
        subjectsTopics: 'Fächer und Themen',
        enterSubjectsTopics: 'Fächer und Themen eingeben',
        durationDays: 'Dauer (in Tagen)',
        howManyDaysStudy: 'Wie viele Tage möchten Sie lernen?',
        dailyStudyHours: 'Tägliche Lernstunden',
        howManyHoursDay: 'Wie viele Stunden können Sie pro Tag lernen?',
        generateMyPlan: 'Meinen Plan Erstellen',
        madeWithForStudents: 'Mit <i class="fas fa-heart"></i> für Studenten gemacht',
        
        readyToStudy: 'Bereit, Klüger zu Lernen?',
        welcomeDescription: 'Erzählen Sie uns von Ihren Fächern und Ihrer Dauer, und wir erstellen eine personalisierte Roadmap, um Ihnen beim Lernen zu helfen!',
        dayWiseSchedule: 'Tagesplan',
        topicBreakdown: 'Themenübersicht',
        freeResources: 'Kostenlose Ressourcen',
        
        craftingStudyPlan: 'Erstelle Ihren perfekten Lernplan...',
        
        keyConcepts: 'Schlüsselkonzepte',
        explanation: 'Erklärung',
        studyPlan: 'Lernplan',
        youtubeTutorials: 'YouTube Tutorials',
        
        markAsComplete: 'Als Erledigt Markieren',
        completed: 'Erledigt',
        
        copiedToClipboard: 'In die Zwischenablage kopiert!',
        failedToCopy: 'Kopieren fehlgeschlagen',
        studyPlanReady: 'Lernplan bereit!',
        failedToGenerate: 'Generierung fehlgeschlagen',
        pleaseFillAllFields: 'Bitte füllen Sie alle Felder aus',
        error: 'Fehler',
        taskMarkedComplete: 'Aufgabe als erledigt markiert!',
        taskUnmarked: 'Aufgabe nicht markiert',
        
        studyPlanDownloaded: 'Lernplan als PDF heruntergeladen!',
        downloadedAsText: 'Als Textdatei heruntergeladen',
        sharedSuccessfully: 'Erfolgreich geteilt!',
        shareCancelled: 'Teilen abgebrochen',
        copiedForSharing: 'In die Zwischenablage zum Teilen kopiert!',
        
        milestoneAchieved: 'Meilenstein Erreicht!',
        completedTasks: 'Sie haben alle Ihre Aufgaben erledigt! Machen Sie weiter!',
        
        noTutorialsFound: 'Keine Tutorials gefunden',
        noExplanationAvailable: 'Keine Erklärung verfügbar',
        
        welcomeBack: 'Willkommen zurück,',
        subjects: 'Fächer',
        duration: 'Dauer',
        dailyHours: 'Tägliche Stunden',
        days: 'Tage',
        hours: 'Stunden',
        
        day: 'Tag',
        
        pdfNotSupported: 'PDF-Generierung wird von diesem Browser nicht unterstützt.',
        downloadTextInstead: 'Möchten Sie stattdessen als Textdatei herunterladen?',
        yes: 'Ja',
        no: 'Nein',
        generatingPdf: 'PDF wird generiert...',
        
        aiStudyPlanner: 'KI Lernplaner',
        smartLearning: 'Intelligentes Lernen'
    },
    zh: {
        yourStudyDashboard: '您的学习面板',
        trackYourStudy: '追踪您的个性化学习之旅',
        theme: '主题',
        copy: '复制',
        download: '下载',
        share: '分享',
        
        yourDetails: '您的详情',
        yourName: '您的姓名',
        enterYourName: '输入您的姓名',
        subjectsTopics: '科目和主题',
        enterSubjectsTopics: '输入科目和主题',
        durationDays: '时长（天）',
        howManyDaysStudy: '您想学习多少天？',
        dailyStudyHours: '每日学习时长',
        howManyHoursDay: '您每天可以学习多少小时？',
        generateMyPlan: '生成我的计划',
        madeWithForStudents: '为学生用 <i class="fas fa-heart"></i> 制作',
        
        readyToStudy: '准备好更聪明地学习了吗？',
        welcomeDescription: '告诉我们您的科目和时长，我们将创建一个个性化的路线图来帮助您学习！',
        dayWiseSchedule: '每日计划',
        topicBreakdown: '主题细分',
        freeResources: '免费资源',
        
        craftingStudyPlan: '正在创建您的完美学习计划...',
        
        keyConcepts: '关键概念',
        explanation: '解释',
        studyPlan: '学习计划',
        youtubeTutorials: 'YouTube 教程',
        
        markAsComplete: '标记为完成',
        completed: '已完成',
        
        copiedToClipboard: '已复制到剪贴板！',
        failedToCopy: '复制失败',
        studyPlanReady: '学习计划已准备好！',
        failedToGenerate: '生成失败',
        pleaseFillAllFields: '请填写所有字段',
        error: '错误',
        taskMarkedComplete: '任务已标记为完成！',
        taskUnmarked: '任务已取消标记',
        
        studyPlanDownloaded: '学习计划已下载为PDF！',
        downloadedAsText: '已下载为文本文件',
        sharedSuccessfully: '分享成功！',
        shareCancelled: '分享已取消',
        copiedForSharing: '已复制到剪贴板以便分享！',
        
        milestoneAchieved: '里程碑达成！',
        completedTasks: '您已完成所有任务！继续加油！',
        
        noTutorialsFound: '未找到教程',
        noExplanationAvailable: '暂无解释',
        
        welcomeBack: '欢迎回来，',
        subjects: '科目',
        duration: '时长',
        dailyHours: '每日时长',
        days: '天',
        hours: '小时',
        
        day: '第',
        
        pdfNotSupported: '此浏览器不支持PDF生成。',
        downloadTextInstead: '您想改用文本文件下载吗？',
        yes: '是',
        no: '否',
        generatingPdf: '正在生成PDF...',
        
        aiStudyPlanner: 'AI学习规划师',
        smartLearning: '智能学习'
    },
    ar: {
        yourStudyDashboard: 'لوحة الدراسة الخاصة بك',
        trackYourStudy: 'تتبع رحلة التعلم الشخصية الخاصة بك',
        theme: 'السمة',
        copy: 'نسخ',
        download: 'تحميل',
        share: 'مشاركة',
        
        yourDetails: 'تفاصيلك',
        yourName: 'اسمك',
        enterYourName: 'أدخل اسمك',
        subjectsTopics: 'المواد والمواضيع',
        enterSubjectsTopics: 'أدخل المواد والمواضيع',
        durationDays: 'المدة (بالأيام)',
        howManyDaysStudy: 'كم يوم تريد الدراسة؟',
        dailyStudyHours: 'ساعات الدراسة اليومية',
        howManyHoursDay: 'كم ساعة يمكنك الدراسة في اليوم؟',
        generateMyPlan: 'إنشاء خطتي',
        madeWithForStudents: 'صنع بـ <i class="fas fa-heart"></i> للطلاب',
        
        readyToStudy: 'هل أنت مستعد للدراسة بشكل أذكى؟',
        welcomeDescription: 'أخبرنا عن موادك ومدة الدراسة، وسنقوم بإنشاء خارطة طريق شخصية لمساعدتك في التعلم!',
        dayWiseSchedule: 'جدول يومي',
        topicBreakdown: 'تفصيل المواضيع',
        freeResources: 'موارد مجانية',
        
        craftingStudyPlan: 'جارٍ إنشاء خطة الدراسة المثالية لك...',
        
        keyConcepts: 'المفاهيم الرئيسية',
        explanation: 'الشرح',
        studyPlan: 'خطة الدراسة',
        youtubeTutorials: 'دروس يوتيوب',
        
        markAsComplete: 'تحديد كمكتمل',
        completed: 'مكتمل',
        
        copiedToClipboard: 'تم النسخ إلى الحافظة!',
        failedToCopy: 'فشل النسخ',
        studyPlanReady: 'خطة الدراسة جاهزة!',
        failedToGenerate: 'فشل الإنشاء',
        pleaseFillAllFields: 'يرجى ملء جميع الحقول',
        error: 'خطأ',
        taskMarkedComplete: 'تم تحديد المهمة كمكتملة!',
        taskUnmarked: 'تم إلغاء تحديد المهمة',
        
        studyPlanDownloaded: 'تم تحميل خطة الدراسة كـ PDF!',
        downloadedAsText: 'تم التحميل كملف نصي',
        sharedSuccessfully: 'تمت المشاركة بنجاح!',
        shareCancelled: 'تم إلغاء المشاركة',
        copiedForSharing: 'تم النسخ إلى الحافظة للمشاركة!',
        
        milestoneAchieved: 'تم تحقيق المعلم!',
        completedTasks: 'لقد أكملت جميع مهامك! استمر!',
        
        noTutorialsFound: 'لم يتم العثور على دروس',
        noExplanationAvailable: 'لا يوجد شرح متاح',
        
        welcomeBack: 'مرحباً بعودتك،',
        subjects: 'المواد',
        duration: 'المدة',
        dailyHours: 'الساعات اليومية',
        days: 'أيام',
        hours: 'ساعات',
        
        day: 'يوم',
        
        pdfNotSupported: 'إنشاء PDF غير مدعوم في هذا المتصفح.',
        downloadTextInstead: 'هل تريد التحميل كملف نصي بدلاً من ذلك؟',
        yes: 'نعم',
        no: 'لا',
        generatingPdf: 'جارٍ إنشاء PDF...',
        
        aiStudyPlanner: 'مخطط دراسة الذكاء الاصطناعي',
        smartLearning: 'تعلم ذكي'
    },
    ja: {
        yourStudyDashboard: '学習ダッシュボード',
        trackYourStudy: 'パーソナライズされた学習の旅を追跡',
        theme: 'テーマ',
        copy: 'コピー',
        download: 'ダウンロード',
        share: '共有',
        
        yourDetails: '詳細情報',
        yourName: 'お名前',
        enterYourName: '名前を入力',
        subjectsTopics: '科目とトピック',
        enterSubjectsTopics: '科目とトピックを入力',
        durationDays: '期間（日数）',
        howManyDaysStudy: '何日間勉強しますか？',
        dailyStudyHours: '1日の勉強時間',
        howManyHoursDay: '1日に何時間勉強できますか？',
        generateMyPlan: 'プランを生成',
        madeWithForStudents: '学生のために <i class="fas fa-heart"></i> で作成',
        
        readyToStudy: 'もっと賢く勉強する準備はできましたか？',
        welcomeDescription: '科目と期間について教えてください。パーソナライズされた学習ロードマップを作成します！',
        dayWiseSchedule: '日別スケジュール',
        topicBreakdown: 'トピック内訳',
        freeResources: '無料リソース',
        
        craftingStudyPlan: '完璧な学習プランを作成中...',
        
        keyConcepts: '重要概念',
        explanation: '説明',
        studyPlan: '学習プラン',
        youtubeTutorials: 'YouTube チュートリアル',
        
        markAsComplete: '完了としてマーク',
        completed: '完了',
        
        copiedToClipboard: 'クリップボードにコピーしました！',
        failedToCopy: 'コピーに失敗しました',
        studyPlanReady: '学習プランの準備ができました！',
        failedToGenerate: '生成に失敗しました',
        pleaseFillAllFields: 'すべてのフィールドを入力してください',
        error: 'エラー',
        taskMarkedComplete: 'タスクを完了としてマークしました！',
        taskUnmarked: 'タスクリセット',
        
        studyPlanDownloaded: '学習プランをPDFでダウンロードしました！',
        downloadedAsText: 'テキストファイルとしてダウンロードしました',
        sharedSuccessfully: '正常に共有しました！',
        shareCancelled: '共有がキャンセルされました',
        copiedForSharing: '共有用にクリップボードにコピーしました！',
        
        milestoneAchieved: 'マイルストーン達成！',
        completedTasks: 'すべてのタスクを完了しました！この調子で！',
        
        noTutorialsFound: 'チュートリアルが見つかりません',
        noExplanationAvailable: '説明がありません',
        
        welcomeBack: 'おかえりなさい、',
        subjects: '科目',
        duration: '期間',
        dailyHours: '1日の時間',
        days: '日',
        hours: '時間',
        
        day: '日目',
        
        pdfNotSupported: 'このブラウザではPDF生成がサポートされていません。',
        downloadTextInstead: '代わりにテキストファイルとしてダウンロードしますか？',
        yes: 'はい',
        no: 'いいえ',
        generatingPdf: 'PDFを生成中...',
        
        aiStudyPlanner: 'AI学習プランナー',
        smartLearning: 'スマート学習'
    },
    pt: {
        yourStudyDashboard: 'Seu Painel de Estudos',
        trackYourStudy: 'Acompanhe sua jornada de aprendizado personalizada',
        theme: 'Tema',
        copy: 'Copiar',
        download: 'Baixar',
        share: 'Compartilhar',
        
        yourDetails: 'Seus Detalhes',
        yourName: 'Seu Nome',
        enterYourName: 'Digite seu nome',
        subjectsTopics: 'Matérias e Tópicos',
        enterSubjectsTopics: 'Digite matérias e tópicos',
        durationDays: 'Duração (em dias)',
        howManyDaysStudy: 'Quantos dias você quer estudar?',
        dailyStudyHours: 'Horas de Estudo Diárias',
        howManyHoursDay: 'Quantas horas você pode estudar por dia?',
        generateMyPlan: 'Gerar Meu Plano',
        madeWithForStudents: 'Feito com <i class="fas fa-heart"></i> para estudantes',
        
        readyToStudy: 'Pronto para Estudar de Forma Mais Inteligente?',
        welcomeDescription: 'Conte-nos sobre suas matérias e duração, e nós criaremos um roteiro personalizado para ajudá-lo a aprender!',
        dayWiseSchedule: 'Cronograma Diário',
        topicBreakdown: 'Detalhamento dos Tópicos',
        freeResources: 'Recursos Gratuitos',
        
        craftingStudyPlan: 'Criando seu plano de estudo perfeito...',
        
        keyConcepts: 'Conceitos-Chave',
        explanation: 'Explicação',
        studyPlan: 'Plano de Estudo',
        youtubeTutorials: 'Tutoriais do YouTube',
        
        markAsComplete: 'Marcar como Concluído',
        completed: 'Concluído',
        
        copiedToClipboard: 'Copiado para a área de transferência!',
        failedToCopy: 'Falha ao copiar',
        studyPlanReady: 'Plano de estudo pronto!',
        failedToGenerate: 'Falha ao gerar',
        pleaseFillAllFields: 'Por favor preencha todos os campos',
        error: 'Erro',
        taskMarkedComplete: 'Tarefa marcada como concluída!',
        taskUnmarked: 'Tarefa desmarcada',
        
        studyPlanDownloaded: 'Plano de estudo baixado como PDF!',
        downloadedAsText: 'Baixado como arquivo de texto',
        sharedSuccessfully: 'Compartilhado com sucesso!',
        shareCancelled: 'Compartilhamento cancelado',
        copiedForSharing: 'Copiado para a área de transferência para compartilhar!',
        
        milestoneAchieved: 'Marco Alcançado!',
        completedTasks: 'Você completou todas as suas tarefas! Continue assim!',
        
        noTutorialsFound: 'Nenhum tutorial encontrado',
        noExplanationAvailable: 'Nenhuma explicação disponível',
        
        welcomeBack: 'Bem-vindo de volta,',
        subjects: 'Matérias',
        duration: 'Duração',
        dailyHours: 'Horas Diárias',
        days: 'dias',
        hours: 'horas',
        
        day: 'Dia',
        
        pdfNotSupported: 'Geração de PDF não é suportada neste navegador.',
        downloadTextInstead: 'Você gostaria de baixar como arquivo de texto?',
        yes: 'Sim',
        no: 'Não',
        generatingPdf: 'Gerando PDF...',
        
        aiStudyPlanner: 'Planejador de Estudos IA',
        smartLearning: 'Aprendizado Inteligente'
    },
    ru: {
        yourStudyDashboard: 'Ваша учебная панель',
        trackYourStudy: 'Отслеживайте свой персонализированный учебный путь',
        theme: 'Тема',
        copy: 'Копировать',
        download: 'Скачать',
        share: 'Поделиться',
        
        yourDetails: 'Ваши данные',
        yourName: 'Ваше имя',
        enterYourName: 'Введите ваше имя',
        subjectsTopics: 'Предметы и темы',
        enterSubjectsTopics: 'Введите предметы и темы',
        durationDays: 'Продолжительность (в днях)',
        howManyDaysStudy: 'Сколько дней вы хотите учиться?',
        dailyStudyHours: 'Часы занятий в день',
        howManyHoursDay: 'Сколько часов в день вы можете учиться?',
        generateMyPlan: 'Создать мой план',
        madeWithForStudents: 'Сделано с <i class="fas fa-heart"></i> для студентов',
        
        readyToStudy: 'Готовы учиться умнее?',
        welcomeDescription: 'Расскажите нам о своих предметах и продолжительности, и мы создадим персонализированный план для вашего обучения!',
        dayWiseSchedule: 'Расписание по дням',
        topicBreakdown: 'Разбивка тем',
        freeResources: 'Бесплатные ресурсы',
        
        craftingStudyPlan: 'Создаем ваш идеальный план обучения...',
        
        keyConcepts: 'Ключевые понятия',
        explanation: 'Объяснение',
        studyPlan: 'План обучения',
        youtubeTutorials: 'YouTube уроки',
        
        markAsComplete: 'Отметить как выполненное',
        completed: 'Выполнено',
        
        copiedToClipboard: 'Скопировано в буфер обмена!',
        failedToCopy: 'Ошибка копирования',
        studyPlanReady: 'План обучения готов!',
        failedToGenerate: 'Ошибка создания',
        pleaseFillAllFields: 'Пожалуйста, заполните все поля',
        error: 'Ошибка',
        taskMarkedComplete: 'Задание отмечено как выполненное!',
        taskUnmarked: 'Задание снято',
        
        studyPlanDownloaded: 'План обучения скачан как PDF!',
        downloadedAsText: 'Скачано как текстовый файл',
        sharedSuccessfully: 'Успешно поделились!',
        shareCancelled: 'Публикация отменена',
        copiedForSharing: 'Скопировано в буфер обмена для публикации!',
        
        milestoneAchieved: 'Веха достигнута!',
        completedTasks: 'Вы выполнили все задания! Продолжайте!',
        
        noTutorialsFound: 'Уроки не найдены',
        noExplanationAvailable: 'Нет объяснения',
        
        welcomeBack: 'С возвращением,',
        subjects: 'Предметы',
        duration: 'Продолжительность',
        dailyHours: 'Часы в день',
        days: 'дней',
        hours: 'часов',
        
        day: 'День',
        
        pdfNotSupported: 'Создание PDF не поддерживается этим браузером.',
        downloadTextInstead: 'Хотите скачать как текстовый файл?',
        yes: 'Да',
        no: 'Нет',
        generatingPdf: 'Создание PDF...',
        
        aiStudyPlanner: 'ИИ Планировщик обучения',
        smartLearning: 'Умное обучение'
    }
};

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');
    
    // Initialize theme
    initTheme();
    
    // Initialize language
    initLanguage();
    
    // Initialize form handler
    initForm();
    
    // Initialize button handlers
    initButtons();
});

// Theme initialization
function initTheme() {
    var themeToggle = document.getElementById('themeToggle');
    var themeIcon = document.getElementById('themeIcon');
    var savedTheme = localStorage.getItem('theme') || 'dark';
    
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (savedTheme === 'light' && themeIcon) {
        themeIcon.classList.remove('fa-moon');
        themeIcon.classList.add('fa-sun');
    }
    
    if (themeToggle) {
        themeToggle.onclick = function() {
            var currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            var icon = document.getElementById('themeIcon');
            if (newTheme === 'light') {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            } else {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        };
    }
}

// Language initialization
function initLanguage() {
    var languageToggle = document.getElementById('languageToggle');
    var languageDropdown = document.getElementById('languageDropdown');
    var currentLangLabel = document.getElementById('currentLangLabel');
    
    var savedLanguage = localStorage.getItem('language') || 'en';
    currentLanguage = savedLanguage;
    
    // Update hidden uiLanguage input field
    var uiLanguageInput = document.getElementById('uiLanguage');
    if (uiLanguageInput) {
        uiLanguageInput.value = savedLanguage;
    }
    
    var langNames = {
        'en': 'English',
        'hi': 'हिंदी',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'zh': '中文',
        'ar': 'العربية',
        'ja': '日本語',
        'pt': 'Português',
        'ru': 'Русский'
    };
    
    if (currentLangLabel) {
        currentLangLabel.textContent = langNames[savedLanguage] || 'English';
    }
    
    applyTranslations(savedLanguage);
    
    if (languageToggle && languageDropdown) {
        languageToggle.onclick = function(e) {
            e.stopPropagation();
            languageDropdown.classList.toggle('show');
        };
        
        document.addEventListener('click', function(e) {
            if (!languageDropdown.contains(e.target)) {
                languageDropdown.classList.remove('show');
            }
        });
        
        var options = languageDropdown.querySelectorAll('.language-option');
        options.forEach(function(option) {
            option.onclick = function() {
                var selectedLang = this.getAttribute('data-lang');
                currentLanguage = selectedLang;
                localStorage.setItem('language', selectedLang);
                
                // Update hidden uiLanguage input field
                var uiLanguageInput = document.getElementById('uiLanguage');
                if (uiLanguageInput) {
                    uiLanguageInput.value = selectedLang;
                }
                
                if (currentLangLabel) {
                    currentLangLabel.textContent = langNames[selectedLang];
                }
                
                applyTranslations(selectedLang);
                languageDropdown.classList.remove('show');
                showToast('Language changed to ' + langNames[selectedLang]);
            };
        });
    }
}

// Apply translations to all text elements
function applyTranslations(lang) {
    var t = translations[lang] || translations['en'];
    
    // Set RTL for Arabic
    if (lang === 'ar') {
        document.documentElement.setAttribute('dir', 'rtl');
        document.documentElement.setAttribute('lang', 'ar');
    } else {
        document.documentElement.setAttribute('dir', 'ltr');
        document.documentElement.setAttribute('lang', lang);
    }
    
    // Header
    var headerH1 = document.querySelector('.header-content h1');
    if (headerH1) headerH1.innerHTML = '<i class="fas fa-sparkles"></i> ' + t.yourStudyDashboard;
    
    var headerP = document.querySelector('.header-content p');
    if (headerP) headerP.textContent = t.trackYourStudy;
    
    var themeSpan = document.querySelector('#themeToggle span');
    if (themeSpan) themeSpan.textContent = t.theme;
    
    var copySpan = document.querySelector('#copyBtn span');
    if (copySpan) copySpan.textContent = t.copy;
    
    var downloadSpan = document.querySelector('#downloadBtn span');
    if (downloadSpan) downloadSpan.textContent = t.download;
    
    var shareSpan = document.querySelector('#shareBtn span');
    if (shareSpan) shareSpan.textContent = t.share;
    
    // Sidebar form
    var formH2 = document.querySelector('.study-form h2');
    if (formH2) formH2.innerHTML = '<i class="fas fa-user-graduate"></i> ' + t.yourDetails;
    
    var nameLabel = document.querySelector('label[for="studentName"]');
    if (nameLabel) nameLabel.textContent = t.yourName;
    
    var nameInput = document.getElementById('studentName');
    if (nameInput) nameInput.placeholder = t.enterYourName;
    
    var subjectsLabel = document.querySelector('label[for="subjects"]');
    if (subjectsLabel) subjectsLabel.textContent = t.subjectsTopics;
    
    var subjectsInput = document.getElementById('subjects');
    if (subjectsInput) subjectsInput.placeholder = t.enterSubjectsTopics;
    
    var durationLabel = document.querySelector('label[for="duration"]');
    if (durationLabel) durationLabel.textContent = t.durationDays;
    
    var durationSmall = document.querySelector('label[for="duration"] + small');
    if (durationSmall) durationSmall.textContent = t.howManyDaysStudy;
    
    var hoursLabel = document.querySelector('label[for="dailyHours"]');
    if (hoursLabel) hoursLabel.textContent = t.dailyStudyHours;
    
    var hoursSmall = document.querySelector('label[for="dailyHours"] + small');
    if (hoursSmall) hoursSmall.textContent = t.howManyHoursDay;
    
    var generateBtn = document.querySelector('.btn-generate');
    if (generateBtn) generateBtn.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> ' + t.generateMyPlan;
    
    var footerP = document.querySelector('.sidebar-footer p');
    if (footerP) footerP.innerHTML = t.madeWithForStudents;
    
    // Logo
    var logoSpan = document.querySelector('.logo-text span');
    if (logoSpan) logoSpan.textContent = t.aiStudyPlanner;
    
    var logoSmall = document.querySelector('.logo-text small');
    if (logoSmall) logoSmall.textContent = t.smartLearning;
    
    // Welcome card
    var welcomeH2 = document.querySelector('.welcome-card h2');
    if (welcomeH2) welcomeH2.textContent = t.readyToStudy;
    
    var welcomeP = document.querySelector('.welcome-card > p');
    if (welcomeP) welcomeP.textContent = t.welcomeDescription;
    
    var features = document.querySelectorAll('.feature span');
    if (features[0]) features[0].textContent = t.dayWiseSchedule;
    if (features[1]) features[1].textContent = t.topicBreakdown;
    if (features[2]) features[2].textContent = t.freeResources;
    
    // Loader
    var loaderText = document.querySelector('.loader-text');
    if (loaderText) loaderText.textContent = t.craftingStudyPlan;
    
    // Celebration
    var celebrationText = document.getElementById('celebrationText');
    if (celebrationText) celebrationText.textContent = t.milestoneAchieved;
    
    var celebrationSubtext = document.getElementById('celebrationSubtext');
    if (celebrationSubtext) celebrationSubtext.textContent = t.completedTasks;
    
    // Update dynamic content (study plan)
    updateDynamicContent(lang);
}

// Update dynamic content (study plan elements)
function updateDynamicContent(lang) {
    var t = translations[lang] || translations['en'];
    
    // Re-render study plan if it exists
    if (currentStudyPlan) {
        renderStudyPlan(currentStudyPlan);
    }
    
    // Section titles
    var sectionTitles = document.querySelectorAll('.section-title');
    sectionTitles.forEach(function(title) {
        var iconClass = title.querySelector('i') ? title.querySelector('i').className : '';
        
        if (iconClass.includes('lightbulb') || title.textContent.includes('Key Concepts') || title.textContent.includes('मुख्य') || title.textContent.includes('Concepts')) {
            title.innerHTML = '<i class="fas fa-lightbulb"></i> ' + t.keyConcepts;
        } else if (iconClass.includes('info') || title.textContent.includes('Explanation') || title.textContent.includes('स्पष्टीकरण') || title.textContent.includes('Explicación')) {
            title.innerHTML = '<i class="fas fa-info-circle"></i> ' + t.explanation;
        } else if (iconClass.includes('tasks') || title.textContent.includes('Study Plan') || title.textContent.includes('अध्ययन') || title.textContent.includes('Plan')) {
            title.innerHTML = '<i class="fas fa-tasks"></i> ' + t.studyPlan;
        } else if (iconClass.includes('youtube') || title.textContent.includes('YouTube')) {
            title.innerHTML = '<i class="fab fa-youtube"></i> ' + t.youtubeTutorials;
        } else if (iconClass.includes('clipboard') || title.textContent.includes('Practice') || title.textContent.includes('अभ्यास') || title.textContent.includes('Práctica')) {
            title.innerHTML = '<i class="fas fa-clipboard-check"></i> ' + t.practiceExamQuestions;
        }
    });
    
    // Update student info card
    var studentInfoCard = document.getElementById('studentInfoCard');
    if (studentInfoCard && studentInfoCard.innerHTML.trim() !== '') {
        var currentHTML = studentInfoCard.innerHTML;
        currentHTML = currentHTML.replace(/Subjects/g, t.subjects);
        currentHTML = currentHTML.replace(/Duration/g, t.duration);
        currentHTML = currentHTML.replace(/Daily Hours/g, t.dailyHours);
        currentHTML = currentHTML.replace(/days/g, t.days);
        currentHTML = currentHTML.replace(/hours/g, t.hours);
        studentInfoCard.innerHTML = currentHTML;
    }
    
    // Update day headers
    var dayHeaders = document.querySelectorAll('.day-info h3');
    dayHeaders.forEach(function(header) {
        var text = header.textContent;
        var match = text.match(/Day\s*(\d+)/i);
        if (match) {
            header.textContent = t.day + ' ' + match[1];
        }
    });
    
    // Update no tutorials text
    var noResources = document.querySelectorAll('.no-resources');
    noResources.forEach(function(el) {
        if (el.textContent.includes('tutorial') || el.textContent.includes('ট্যুটোরিয়াল')) {
            el.textContent = t.noTutorialsFound;
        } else if (el.textContent.includes('explanation') || el.textContent.includes('স্পষ্টীকরণ')) {
            el.textContent = t.noExplanationAvailable;
        }
    });
    
    // Update checkboxes labels
    var checkboxLabels = document.querySelectorAll('.checkbox-label');
    checkboxLabels.forEach(function(label) {
        if (label.textContent.includes('Mark as Complete') || label.textContent.includes('पूर्ण') || label.textContent.includes('Marcar') || label.textContent.includes('Marquer') || label.textContent.includes('Markieren') || label.textContent.includes('Complete')) {
            label.textContent = t.completed;
        }
    });
}

// Form handler
function initForm() {
    var form = document.getElementById('studyForm');
    if (!form) return;
    
    form.onsubmit = function(e) {
        e.preventDefault();
        generatePlan();
    };
}

// Button handlers
function initButtons() {
    var copyBtn = document.getElementById('copyBtn');
    if (copyBtn) {
        copyBtn.onclick = function() {
            if (currentStudyPlan) {
                var text = formatStudyPlanAsText(currentStudyPlan);
                navigator.clipboard.writeText(text).then(function() {
                    showToast('Copied to clipboard!');
                }).catch(function() {
                    showToast('Failed to copy', 'error');
                });
            }
        };
    }
    
    var downloadBtn = document.getElementById('downloadBtn');
    if (downloadBtn) {
        downloadBtn.onclick = function() {
            if (currentStudyPlan) {
                downloadStudyPlan(currentStudyPlan);
            }
        };
    }
    
    var shareBtn = document.getElementById('shareBtn');
    if (shareBtn) {
        shareBtn.onclick = function() {
            if (currentStudyPlan) {
                shareStudyPlan(currentStudyPlan);
            }
        };
    }
}

// Generate plan function
function generatePlan() {
    var name = document.getElementById('studentName').value.trim();
    var subjects = document.getElementById('subjects').value.trim();
    var duration = document.getElementById('duration').value;
    var dailyHours = document.getElementById('dailyHours').value;
    
    if (!name || !subjects || !duration || !dailyHours) {
        showToast('Please fill all fields', 'error');
        return;
    }
    
    var generateBtn = document.getElementById('generateBtn');
    var ripple = document.createElement('span');
    ripple.classList.add('ripple');
    generateBtn.appendChild(ripple);
    
    var rect = generateBtn.getBoundingClientRect();
    var diameter = Math.max(rect.width, rect.height);
    ripple.style.width = ripple.style.height = diameter + 'px';
    ripple.style.left = '0';
    ripple.style.top = '0';
    
    setTimeout(function() {
        ripple.remove();
    }, 600);
    
    document.getElementById('loader').style.display = 'flex';
    document.getElementById('welcomeCard').style.display = 'none';
    
    var uiLanguageInput = document.getElementById('uiLanguage');
    var uiLanguage = uiLanguageInput ? uiLanguageInput.value : 'english';

    fetch('/generate-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            studentName: name,
            subjects: subjects,
            duration: duration,
            dailyHours: parseInt(dailyHours),
            ui_language: uiLanguage   
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        document.getElementById('loader').style.display = 'none';
        
        if (data.success) {
            currentStudyPlan = data.study_plan;
            document.getElementById('studyPlanContainer').style.display = 'block';
            document.getElementById('headerActions').style.display = 'flex';
            renderStudyPlan(data.study_plan);
            showToast('Study plan ready!');
        } else {
            document.getElementById('welcomeCard').style.display = 'block';
            showToast(data.error || 'Failed to generate', 'error');
        }
    })
    .catch(function(error) {
        document.getElementById('loader').style.display = 'none';
        document.getElementById('welcomeCard').style.display = 'block';
        showToast('Error: ' + error.message, 'error');
    });
}

// Render study plan
function renderStudyPlan(studyPlan) {
    var studentInfoCard = document.getElementById('studentInfoCard');
    var studyPlanDiv = document.getElementById('studyPlan');
    
    currentStudyPlan = studyPlan;
    var currentHash = JSON.stringify(studyPlan.student_info.name + studyPlan.total_days);
    var storedHash = localStorage.getItem('currentStudyPlanHash') || '';
    
    if (storedHash !== currentHash) {
        taskCompletion = {};
        localStorage.setItem('taskCompletion', JSON.stringify(taskCompletion));
        localStorage.setItem('currentStudyPlanHash', currentHash);
    } else {
        var savedTasks = JSON.parse(localStorage.getItem('taskCompletion') || '{}');
        taskCompletion = savedTasks;
    }
    
    totalTasks = 0;
    studyPlan.study_plan.forEach(function(day) {
        totalTasks += day.topics.length;
    });
    
    var student = studyPlan.student_info;
    studentInfoCard.innerHTML = '<h3>Welcome back, ' + student.name + '!</h3>' +
        '<div class="student-info-grid">' +
        '<div class="info-item"><label>Subjects</label><span>' + student.subjects + '</span></div>' +
        '<div class="info-item"><label>Duration</label><span>' + (student.duration || student.total_days + ' days') + '</span></div>' +
        '<div class="info-item"><label>Daily Hours</label><span>' + student.daily_hours + ' hours</span></div></div>';
    
    studyPlanDiv.innerHTML = '';
    
    var topicIcons = ['fa-book', 'fa-atom', 'fa-calculator', 'fa-code', 'fa-flask', 'fa-globe'];
    
    studyPlan.study_plan.forEach(function(day, index) {
        var dayCard = document.createElement('div');
        dayCard.className = 'day-card';
        
        var topicsHTML = '';
        day.topics.forEach(function(topic, tIndex) {
            var topicId = 'topic-' + day.day + '-' + tIndex;
            var isCompleted = taskCompletion[topicId] || false;
            var icon = topicIcons[tIndex % topicIcons.length];
            
            // Format explanation as bullet points
            var explanationText = topic.explanation || 'No explanation available';
            var explanationHtml = '';
            if (explanationText && explanationText !== 'No explanation available') {
                var sentences = explanationText.split('. ').filter(function(s) { return s.trim().length > 0; });
                if (sentences.length > 1) {
                    explanationHtml = '<ul class="explanation-list">';
                    sentences.forEach(function(sentence) {
                        var trimmed = sentence.trim();
                        if (trimmed && !trimmed.endsWith('.')) {
                            trimmed += '.';
                        }
                        if (trimmed) {
                            explanationHtml += '<li>' + trimmed + '</li>';
                        }
                    });
                    explanationHtml += '</ul>';
                } else {
                    explanationHtml = '<p>' + explanationText + '</p>';
                }
            } else {
                explanationHtml = '<p>' + explanationText + '</p>';
            }
            
            // Key concepts
            var conceptsHtml = '';
            if (topic.key_concepts) {
                conceptsHtml = topic.key_concepts.map(function(c) { return '<li>' + c + '</li>'; }).join('');
            }
            
            // YouTube Tutorial cards (video cards with thumbnails)
            var tutorialHtml = '';
            if (topic.youtube_resources && topic.youtube_resources.length > 0) {
                tutorialHtml = '<div class="youtube-cards-container">';
                topic.youtube_resources.forEach(function(yt) {
                    var videoId = '';
                    var title = '';
                    var channel = '';
                    var duration = '';
                    var thumbnail = '';
                    var url = '';
                    var isValidVideo = false;
                    
                    // Handle both full video objects and URL strings
                    if (typeof yt === 'object' && yt !== null) {
                        videoId = yt.video_id || '';
                        title = yt.title || 'Video Tutorial';
                        channel = yt.channel || 'YouTube';
                        duration = yt.duration || '';
                        thumbnail = yt.thumbnail || '';
                        url = yt.url || '';
                        
                        // Validate video_id - must be 11 character alphanumeric
                        if (videoId && videoId.length === 11 && /^[a-zA-Z0-9_-]{11}$/.test(videoId)) {
                            isValidVideo = true;
                        }
                        
                        // If no video_id but have URL, try to extract
                        if (!videoId && url) {
                            if (url.includes('youtube.com/watch?v=')) {
                                var match = url.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
                                if (match) {
                                    videoId = match[1];
                                    isValidVideo = true;
                                }
                            } else if (url.includes('youtu.be/')) {
                                var shortId = url.split('youtu.be/')[1];
                                if (shortId) {
                                    shortId = shortId.split('?')[0].split('&')[0];
                                    if (shortId.length === 11) {
                                        videoId = shortId;
                                        isValidVideo = true;
                                    }
                                }
                            }
                        }
                    } else if (typeof yt === 'string') {
                        // Handle string URLs
                        url = yt;
                        if (url.includes('youtube.com/watch?v=')) {
                            var match = url.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
                            if (match) {
                                videoId = match[1];
                                isValidVideo = true;
                                title = 'YouTube Tutorial';
                            }
                        } else if (url.includes('youtu.be/')) {
                            var shortId = url.split('youtu.be/')[1];
                            if (shortId) {
                                shortId = shortId.split('?')[0].split('&')[0];
                                if (shortId.length === 11) {
                                    videoId = shortId;
                                    isValidVideo = true;
                                    title = 'YouTube Tutorial';
                                }
                            }
                        } else {
                            // Fallback search URL - not a playable video
                            title = 'Search YouTube';
                            channel = 'YouTube';
                        }
                    }
                    
                    // Generate proper thumbnail URL if we have valid videoId
                    if (!thumbnail && videoId) {
                        thumbnail = 'https://img.youtube.com/vi/' + videoId + '/hqdefault.jpg';
                    } else if (!thumbnail && url) {
                        // Try extracting from URL if not set
                        if (url.includes('youtube.com/watch?v=')) {
                            var match = url.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
                            if (match) {
                                thumbnail = 'https://img.youtube.com/vi/' + match[1] + '/hqdefault.jpg';
                            }
                        }
                    }
                    
                    // Render video card ONLY if we have valid videoId (STRICT)
                    if (videoId && isValidVideo) {
                        var imgSrc = thumbnail || 'https://img.youtube.com/vi/' + videoId + '/hqdefault.jpg';
                        var playButton = '<div class="play-overlay"><i class="fas fa-play-circle"></i></div>';
                        
                        tutorialHtml += '<div class="youtube-card" data-video-id="' + videoId + '" onclick="playYouTubeVideo(this, \'' + videoId + '\')">' +
                            '<div class="youtube-card-thumbnail">' +
                            '<img src="' + imgSrc + '" alt="' + title + '" ' +
                            'onerror="this.onerror=null; this.src=\'https://img.youtube.com/vi/' + videoId + '/mqdefault.jpg\'" ' +
                            'onload="this.classList.add(\'loaded\')">' + playButton;
                        
                        if (duration) {
                            tutorialHtml += '<span class="video-duration">' + duration + '</span>';
                        }
                        
                        tutorialHtml += '</div>' +
                            '<div class="youtube-card-info">' +
                            '<h4 class="youtube-card-title">' + title + '</h4>' +
                            '<p class="youtube-card-channel"><i class="fas fa-user-circle"></i> ' + channel + '</p>' +
                            '</div>' +
                            '</div>';
                    }
                });
                tutorialHtml += '</div>';
            } else {
                tutorialHtml = '<div class="no-resources">No tutorials found</div>';
            }
            
            // Study plan
            var studyPlanHtml = '';
            if (topic.study_plan) {
                studyPlanHtml = topic.study_plan.map(function(s) { return '<li>' + s + '</li>'; }).join('');
            }
            
            // Mark as complete checkbox - unchecked by default
            var checkboxLabel = isCompleted ? translations[currentLanguage].completed : translations[currentLanguage].markAsComplete;
            var markCompleteBtn = '<div class="mark-complete-container">' +
                '<label class="mark-complete-checkbox">' +
                '<input type="checkbox" data-topic-id="' + topicId + '" onchange="toggleTaskComplete(\'' + topicId + '\')" ' + (isCompleted ? 'checked' : '') + '>' +
                '<span class="checkbox-custom"></span>' +
                '<span class="checkbox-label">' + checkboxLabel + '</span>' +
                '</label>' +
                '</div>';
            
            topicsHTML += '<div class="topic-card ' + (isCompleted ? 'completed' : '') + '" id="' + topicId + '">' +
                '<div class="topic-header">' +
                '<div class="topic-icon"><i class="fas ' + icon + '"></i></div>' +
                '<div><h4>' + topic.topic_name + '</h4><span class="time-badge">' + (topic.time || '60 min') + '</span></div>' +
                '</div>' +
                '<div class="section-title"><i class="fas fa-lightbulb"></i> Key Concepts</div>' +
                '<ul class="concepts-list">' + conceptsHtml + '</ul>' +
                '<div class="section-title"><i class="fas fa-info-circle"></i> Explanation</div>' +
                '<div class="explanation">' + explanationHtml + '</div>' +
                '<div class="section-title"><i class="fas fa-tasks"></i> Study Plan</div>' +
                '<ul class="study-plan-list">' + studyPlanHtml + '</ul>' +
                '<div class="section-title"><i class="fab fa-youtube"></i> YouTube Tutorials</div>' +
                '<ul class="resources-list tutorial-list">' + tutorialHtml + '</ul>' +
                markCompleteBtn + '</div>';
        });
        
        var dayNumber = String(day.day).padStart(2, '0');
        dayCard.innerHTML = '<div class="day-header">' +
            '<div class="day-number"><div class="day-badge">' + dayNumber + '</div>' +
            '<div class="day-info"><h3>Day ' + dayNumber + '</h3><p>' + day.date + '</p></div></div>' +
            '<div class="subject-badge">' + day.subject + '</div></div>' +
            '<div class="day-content">' + topicsHTML + '</div>';
        
        studyPlanDiv.appendChild(dayCard);
    });
}

// Format study plan as text
function formatStudyPlanAsText(studyPlan) {
    var text = 'AI STUDY PLAN\n\n';
    text += 'Student: ' + studyPlan.student_info.name + '\n';
    text += 'Subjects: ' + studyPlan.student_info.subjects + '\n';
    text += 'Duration: ' + (studyPlan.student_info.duration || studyPlan.total_days + ' days') + '\n';
    text += 'Daily Hours: ' + studyPlan.student_info.daily_hours + '\n\n';
    
    studyPlan.study_plan.forEach(function(day) {
        text += '\n--- DAY ' + day.day + ' ---\n';
        text += 'Subject: ' + day.subject + '\n\n';
        
        day.topics.forEach(function(topic) {
            text += 'Topic: ' + topic.topic_name + '\n';
            text += 'Time: ' + (topic.time || '60 min') + '\n\n';
            text += 'Explanation:\n' + (topic.explanation || '') + '\n\n';
            
            if (topic.key_concepts) {
                text += 'Key Concepts:\n';
                topic.key_concepts.forEach(function(c) {
                    text += '- ' + c + '\n';
                });
                text += '\n';
            }
            
            if (topic.study_plan) {
                text += 'Study Plan:\n';
                topic.study_plan.forEach(function(s, i) {
                    text += (i+1) + '. ' + s + '\n';
                });
                text += '\n';
            }
            
            if (topic.youtube_resources) {
                text += 'YouTube:\n';
                topic.youtube_resources.forEach(function(y) {
                    text += '- ' + y + '\n';
                });
                text += '\n';
            }
        });
    });
    
    return text;
}

// Download study plan as PDF
function downloadStudyPlan(studyPlan) {
    var downloadBtn = document.getElementById('downloadBtn');
    if (downloadBtn) downloadBtn.disabled = true;
    showToast('Generating PDF...');
    
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/download-pdf', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.responseType = 'blob';
    
    xhr.onload = function() {
        if (downloadBtn) downloadBtn.disabled = false;
        
        if (xhr.status === 200) {
            var blob = xhr.response;
            var contentType = xhr.getResponseHeader('Content-Type');
            
            if (contentType && contentType.includes('application/pdf')) {
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = (studyPlan.student_info && studyPlan.student_info.name ? studyPlan.student_info.name : 'Study_Plan') + '_Study_Plan.pdf';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                showToast('Study plan downloaded as PDF!');
            } else {
                showToast('PDF generation failed', 'error');
                downloadAsText(studyPlan);
            }
        } else {
            showToast('Download failed: ' + xhr.status, 'error');
            downloadAsText(studyPlan);
        }
    };
    
    xhr.onerror = function() {
        if (downloadBtn) downloadBtn.disabled = false;
        showToast('Network error', 'error');
        downloadAsText(studyPlan);
    };
    
    xhr.send(JSON.stringify({
        study_plan: studyPlan
    }));
}

function downloadAsText(studyPlan) {
    var text = formatStudyPlanAsText(studyPlan);
    var blob = new Blob([text], { type: 'text/plain' });
    var url = window.URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = (studyPlan.student_info && studyPlan.student_info.name ? studyPlan.student_info.name : 'Study_Plan') + '_Study_Plan.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    showToast('Downloaded as text file');
}

// Share study plan
function shareStudyPlan(studyPlan) {
    var text = formatStudyPlanAsText(studyPlan);
    var shareData = {
        title: 'My AI Study Plan',
        text: text
    };
    
    if (navigator.share) {
        navigator.share(shareData).then(function() {
            showToast('Shared successfully!');
        }).catch(function() {
            showToast('Share cancelled', 'error');
        });
    } else {
        navigator.clipboard.writeText(text).then(function() {
            showToast('Copied to clipboard for sharing!');
        }).catch(function() {
            showToast('Failed to copy', 'error');
        });
    }
}

// Show toast notification
function showToast(message, type) {
    var toast = document.getElementById('toast');
    var icon = type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle';
    toast.innerHTML = '<i class="fas ' + icon + '"></i> ' + message;
    toast.className = 'toast ' + (type || 'success') + ' show';
    
    setTimeout(function() {
        toast.classList.remove('show');
    }, 3000);
}

// Toggle task completion (checkbox-based)
function toggleTaskComplete(topicId) {
    var card = document.getElementById(topicId);
    var checkbox = card.querySelector('.mark-complete-checkbox input[type="checkbox"]');
    var label = card.querySelector('.checkbox-label');
    var isCompleted = checkbox.checked;
    var t = translations[currentLanguage] || translations['en'];
    
    taskCompletion[topicId] = isCompleted;
    localStorage.setItem('taskCompletion', JSON.stringify(taskCompletion));
    
    if (isCompleted) {
        card.classList.add('completed');
        label.textContent = t.completed;
        showToast(t.taskMarkedComplete);
        checkMilestone();
    } else {
        card.classList.remove('completed');
        label.textContent = t.markAsComplete;
        showToast(t.taskUnmarked);
    }
}

// Check if milestone achieved
function checkMilestone() {
    var completedCount = Object.keys(taskCompletion).filter(function(key) {
        return taskCompletion[key];
    }).length;
    
    if (completedCount === totalTasks && totalTasks > 0) {
        showMilestoneCelebration(completedCount);
    }
}

// Show milestone celebration with fireworks
function showMilestoneCelebration(count) {
    var container = document.getElementById('celebrationContainer');
    var confetti = document.getElementById('confetti');
    var celebrationText = document.getElementById('celebrationText');
    var subtext = document.getElementById('celebrationSubtext');
    
    celebrationText.textContent = 'Milestone Achieved!';
    subtext.textContent = 'You have completed ' + count + ' tasks! Keep going!';
    
    container.classList.add('active');
    
    createConfetti();
    
    setTimeout(function() {
        container.classList.remove('active');
    }, 4000);
}

// Create confetti particles
function createConfetti() {
    var confetti = document.getElementById('confetti');
    confetti.innerHTML = '';
    
    var colors = ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff', '#5f27cd', '#ee5a24', '#009432'];
    
    for (var i = 0; i < 100; i++) {
        var piece = document.createElement('div');
        piece.className = 'confetti-piece';
        piece.style.left = Math.random() * 100 + '%';
        piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        piece.style.animationDuration = (Math.random() * 2 + 2) + 's';
        piece.style.animationDelay = Math.random() * 0.5 + 's';
        
        var shapes = ['square', 'circle'];
        piece.style.borderRadius = shapes[Math.floor(Math.random() * shapes.length)] === 'circle' ? '50%' : '0';
        
        confetti.appendChild(piece);
    }
}

console.log('script.js loaded');
