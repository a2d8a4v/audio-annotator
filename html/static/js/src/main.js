'use strict';

/*
 * Purpose:
 *   Combines all the components of the interface. Creates each component, gets task
 *   data, updates components. When the user submits their work this class gets the workers
 *   annotations and other data and submits to the backend
 * Dependencies:
 *   AnnotationStages (src/annotation_stages.js), PlayBar & WorkflowBtns (src/components.js), 
 *   HiddenImg (src/hidden_image.js), colormap (colormap/colormap.min.js) , Wavesurfer (lib/wavesurfer.min.js)
 * Globals variable from other files:
 *   colormap.min.js:
 *       magma // color scheme array that maps 0 - 255 to rgb values
 *    
 */
function Annotator() {
    this.wavesurfer;
    this.playBar;
    this.stages;
    this.workflowBtns;
    this.currentTask;
    this.taskStartTime;
    this.hiddenImage;
    // only automatically open instructions modal when first loaded
    this.instructionsViewed = false;
    // Boolean, true if currently sending http post request 
    this.sendingResponse = false;

    // Create color map for spectrogram
    var spectrogramColorMap = colormap({
        colormap: magma,
        nshades: 256,
        format: 'rgb',
        alpha: 1
    });

    // Create wavesurfer (audio visualization component)
    var height = 256;
    var minPxPerSec = 256;
    this.wavesurfer = Object.create(WaveSurfer);
    this.wavesurfer.init({
        container: '.audio_visual',
        waveColor: '#FF00FF',
        progressColor: '#FF00FF',
        // For the spectrogram the height is half the number of fftSamples
        fftSamples: height * 2,
        height: height,
        fillParent: false,
        minPxPerSec: minPxPerSec,
        colorMap: spectrogramColorMap
    });

    // Create labels (labels that appear above each region)
    var labels = Object.create(WaveSurfer.Labels);
    labels.init({
        wavesurfer: this.wavesurfer,
        container: '.labels',
        deletebutton: false,
    });

    // Create hiddenImage, an image that is slowly revealed to a user as they annotate 
    // (only for this.currentTask.feedback === 'hiddenImage')
    this.hiddenImage = new HiddenImg('.hidden_img', 100);
    this.hiddenImage.create();

    // Create the play button and time that appear below the wavesurfer
    this.playBar = new PlayBar(this.wavesurfer);
    this.playBar.create();

    // Create the annotation stages that appear below the wavesurfer. The stages contain tags 
    // the users use to label a region in the audio clip
    this.stages = new AnnotationStages(this.wavesurfer, this.hiddenImage);
    this.stages.create();

    // Create Workflow btns (submit and exit)
    this.workflowBtns = new WorkflowBtns();
    this.workflowBtns.create();

    this.addEvents();
}

Annotator.prototype = {
    addWaveSurferEvents: function () {
        var my = this;

        // function that moves the vertical progress bar to the current time in the audio clip
        var updateProgressBar = function () {
            var progress = my.wavesurfer.getCurrentTime() / my.wavesurfer.getDuration();
            my.wavesurfer.seekTo(progress);
        };

        // Update vertical progress bar to the currentTime when the sound clip is 
        // finished or paused since it is only updated on audioprocess
        this.wavesurfer.on('pause', updateProgressBar);
        this.wavesurfer.on('finish', updateProgressBar);

        // When a new sound file is loaded into the wavesurfer update the  play bar, update the 
        // annotation stages back to stage 1, update when the user started the task, update the workflow buttons.
        // Also if the user is suppose to get hidden image feedback, append that component to the page
        this.wavesurfer.on('ready', function () {
            my.playBar.update();
            my.stages.updateStage(1);
            my.updateTaskTime();
            my.workflowBtns.update();
            if (my.currentTask.feedback === 'hiddenImage') {
                my.hiddenImage.append(my.currentTask.imgUrl);
            }

            // 加载已标注结果
            if (my.currentTask.annotations.length > 0) {
                for (var i = 0; i < my.currentTask.annotations.length; i++) {
                    var annotation = my.currentTask.annotations[i];
                    annotation.drag = false;
                    annotation.resize = false;
                    var region = my.wavesurfer.addRegion(annotation);
                    my.stages.updateStage(3, region);
                }
            }
        });

        this.wavesurfer.on('click', function (e) {
            my.stages.clickDeselectCurrentRegion();
        });
    },

    addTierInputs: function () {
        var my = this;
        var wait;


    },

    addScoreInputs: function () {
        var my = this;
        var wait

        wait = new Promise((resolve, reject) => {
            if (my.currentTask) {
                resolve(my.currentTask.annotationScore);
            } else {
                // Optional: Retry mechanism if it's expected to load soon
                const interval = setInterval(() => {
                    if (my.currentTask) {
                        clearInterval(interval);
                        resolve(my.currentTask.annotationScore);
                    }
                }, 100); // Check every 100ms
            }
        });
        wait.then((content) => {
            function tryUpdateInputs(retries = 5) {
                // Loop through the annotation scores
                $.each(content, function(key, value) {
                    // Find the input element by its id
                    var $input = $('#' + key);
                    // If the input is found, update the value
                    if ($input.length) {
                        $input.val(value);
                    } else if (retries > 0) {
                        // Retry after a short delay if the input doesn't exist yet
                        setTimeout(() => tryUpdateInputs(retries - 1), 100); // Retry after 100ms
                    } else {
                        console.warn('Input with id "' + key + '" not found after retries.');
                    }
                });
            }
        
            // Call the function to try updating the inputs
            tryUpdateInputs();
        }).catch((error) => {
            console.error('Error:', error);
        });

    },

    updateTaskTime: function () {
        this.taskStartTime = new Date().getTime();
    },

    // Event Handler, if the user clicks submit annotations call submitAnnotations
    addWorkflowBtnEvents: function () {
        $(this.workflowBtns).on('submit-annotations', this.submitAnnotations.bind(this));
    },

    addEvents: function () {
        this.addWaveSurferEvents();
        this.addTierInputs();
        this.addScoreInputs();
        this.addWorkflowBtnEvents();
    },

    // Update the task specific data of the interfaces components
    update: function () {
        var my = this;
        var mainUpdate = function (annotationSolutions) {

            // Update the different tags the user can use to annotate, also update the solutions to the
            // annotation task if the user is suppose to recieve feedback
            var annotationTiers = my.currentTask.annotationTier;
            var proximityTags = my.currentTask.proximityTag;
            var annotationTags = my.currentTask.annotationTag;
            var annotationUtteranceScores = my.currentTask.annotationUtteranceScore;
            var annotationWordScores = my.currentTask.annotationScore;
            var annotationPhoneScores = my.currentTask.annotationScore;
            var alignCollect = my.currentTask.alignCollect;

            var tutorialVideoURL = my.currentTask.tutorialVideoURL;
            var alwaysShowTags = my.currentTask.alwaysShowTags;
            var instructions = my.currentTask.instructions;

            my.stages.reset(
                alignCollect,
                annotationTiers,
                proximityTags,
                annotationTags,
                annotationUtteranceScores,
                annotationSolutions,
                alwaysShowTags,
                my.wavesurfer.regions
            );

            // set video url
            $('#tutorial-video').attr('src', tutorialVideoURL);

            // add instructions
            var instructionsContainer = $('#instructions-container');
            instructionsContainer.empty();
            if (typeof instructions !== "undefined") {
                $('.modal-trigger').leanModal();
                instructions.forEach(function (instruction, index) {
                    if (index == 0) {
                        // first instruction is the header
                        var instr = $('<h4>', {
                            html: instruction
                        });
                    } else {
                        var instr = $('<h6>', {
                            "class": "instruction",
                            html: instruction
                        });
                    }
                    instructionsContainer.append(instr);
                });
                if (!my.instructionsViewed) {
                    $('#instructions-modal').openModal();
                    my.instructionsViewed = true;
                }
            }
            else {
                $('#instructions-container').hide();
                $('#trigger').hide();
            }

            var uttid = my.currentTask.uttid;
            var filename_without_extension = my.currentTask.filename_without_extension
            $('#wav_url').html(filename_without_extension + ' - ' + uttid);

            // Update the visualization type and the feedback type and load in the new audio clip
            my.wavesurfer.params.visualization = my.currentTask.visualization; // invisible, spectrogram, waveform
            my.wavesurfer.params.feedback = my.currentTask.feedback; // hiddenImage, silent, notify, none 
            // Decode Base64 audio data to binary
            const base64String = my.currentTask.wav_binary;
            const binaryString = atob(base64String);  // Decode Base64 to binary string

            // Convert binary string to Uint8Array
            const byteArray = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                byteArray[i] = binaryString.charCodeAt(i);
            }

            // Create a Blob from the binary data
            const blob = new Blob([byteArray], { type: 'audio/wav' });

            // Load Blob into WaveSurfer
            my.wavesurfer.loadBlob(blob);
        };

        if (this.currentTask.feedback !== 'none') {
            // If the current task gives the user feedback, load the tasks solutions and then update
            // interface components
            $.getJSON(this.currentTask.annotationSolutionsUrl)
                .done(function (data) {
                    mainUpdate(data);
                })
                .fail(function () {
                    alert('错误: 无法检索标注解决方案');
                });
        } else {
            // If not, there is no need to make an additional request. Just update task specific data right away
            mainUpdate({});
        }
    },

    // Update the interface with the next task's data
    loadNextTask: function () {
        var my = this;
        var get_task_url = dataUrl;
        get_task_url = dataUrl + window.location.search;
        $.getJSON(get_task_url)
            .done(function (data) {
                var ret = data.ret;
                if (ret === "no_tasks") {
                    alert("没有更多任务了")
                }
                else if (ret === "ok") {
                    my.currentTask = data.task;
                    my.update();
                }
            });

    },

    // Collect data about users annotations and submit it to the backend
    submitAnnotations: function () {
        // Check if all the regions have been labeled before submitting
        if (this.stages.annotationDataValidationCheck()) {
            if (this.sendingResponse) {
                // If it is already sending a post with the data, do nothing
                return;
            }
            this.sendingResponse = true;
            // Get data about the annotations the user has created
            var content = {
                task: this.currentTask,
                task_start_time: this.taskStartTime,
                task_end_time: new Date().getTime(),
                visualization: this.wavesurfer.params.visualization,
                annotations: this.stages.getAnnotations(),
                utt_score_annotations: this.stages.getUttScoreAnnotations(),
                word_score_annotatoins: this.stages.getWordScoreAnnotations(),
                phone_score_annotations: this.stages.getPhoneScoreAnnotations(),
                deleted_annotations: this.stages.getDeletedAnnotations(),
                // List of the different types of actions they took to create the annotations
                annotation_events: this.stages.getEvents(),
                // List of actions the user took to play and pause the audio
                play_events: this.playBar.getEvents(),
                // Boolean, if at the end, the user was shown what city the clip was recorded in
                final_solution_shown: this.stages.aboveThreshold()
            };

            if (this.stages.aboveThreshold()) {
                // If the user is suppose to recieve feedback and got enough of the annotations correct
                // display the city the clip was recorded for 2 seconds and then submit their work
                var my = this;
                this.stages.displaySolution();
                setTimeout(function () {
                    my.post(content);
                }, 2000);
            } else {
                this.post(content);
            }
        }
    },

    // Make POST request, passing back the content data. On success load in the next task
    post: function (content) {
        var my = this;
        $.ajax({
            type: 'POST',
            url: postUrl,
            contentType: 'application/json',
            data: JSON.stringify(content),
            success: function (data) {
                data = JSON.parse(data);
                if (data.ret === "ok") {
                    console.log(data.msg);
                    // If the last task had a hiddenImage component, remove it
                    if (my.currentTask.feedback === 'hiddenImage') {
                        my.hiddenImage.remove();
                    }
                    my.loadNextTask();

                } else if (data.ret === "file_exsit") {
                    alert(data.msg);
                    // If the last task had a hiddenImage component, remove it
                    if (my.currentTask.feedback === 'hiddenImage') {
                        my.hiddenImage.remove();
                    }
                    my.loadNextTask();
                } else if (data.ret === "error") {
                    alert("结果提交出错: " + data.msg)
                }

            },
            error: function () {
                alert('错误：无法提交标注结果');
            },
            complete: function () {
                // No longer sending response
                my.sendingResponse = false;
            }
        })
    }

};

function main() {
    // Create all the components
    var annotator = new Annotator();
    // Load the first audio annotation task
    annotator.loadNextTask();
}

main();
