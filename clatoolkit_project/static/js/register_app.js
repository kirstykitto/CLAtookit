// Vue App for the Home/Login and class registration

new Vue({
    el: '#register-form',

    data: {
        social_accounts: [],
        fb: false,
        tw: false,
        yt: false,
        tr: false,
        twitter_acc_index: null,
        lrs_error: '',
        form_errors: {user_form: {username: '', password: '', email:''}, profile_form: {
          fb_id: '',
          twitter_id: '',
          forum_id: '',
          google_account_name: '',
          github_account_name: '',
          trello_account_name: '',
          blog_id: '',
          diigo_id: ''
        }},
        social_account: {platform: '', id: '', thumbnail: '', name: ''},
        account: {username: '', email: '', password: ''}
        //username: 'somones username'
    },

    ready: function () {

    },

    methods: {

        submit: function(e) {
          e.preventDefault();
          this.form_errors = this.reset_form_errors();
          // data will have user/email/pass, since these aren't handled by the underlying vue data model
          // we'll get social IDs from data model, through

          // Build Social account form for django
          let social_media_map = {
            'facebook': 'fb_id',
            'twitter': 'twitter_id',
            'forum': 'forum_id',
            'youtube': 'google_account_name',
            'github': 'github_account_name',
            'trello': 'trello_account_name',
            'blog': 'blog_id',
            'diigo': 'diigo_username'
          };

          // Build user profile form
          let userProfile_form = {}

          for (let i=0; i<this.social_accounts.length; i++) {
            let social_accounts = this.social_accounts;

            if (social_accounts[i].platform == 'twitter') {
              // We do this here since Twitter isn't automated
              //console.log(social_media_map[social_accounts[i].platform]);
              //console.log(social_accounts[i].name);
              userProfile_form[social_media_map[social_accounts[i].platform]] = social_accounts[i].name;
            } else {
              userProfile_form[social_media_map[social_accounts[i].platform]] = social_accounts[i].id;
            }
          }

          // Get django csrf token (required to send data to django back-end manually)
          csrf_token = document.getElementById("register-form").elements["csrfmiddlewaretoken"].value;

          // Send form data to django framework
          let data = {user_profile: userProfile_form, user_account: this.account};

          // POST Request for signup
          this.$http.post(window.location.href, data, {
            headers: {
              'X-CSRFToken': csrf_token
            }
          })
            .then(function(response){
              // redirect to dashboard
              window.location = window.location.origin + response.data
            })
            .catch(function(response){
              console.error("Error creating CLAToolkit account:")
              console.error(response);

              if (response.status == 400) {
                this.form_errors = response.data.errors;
              }

              if (response.status == 503) {
                console.log("LRS ERROR!!");
                this.lrs_error = response.data;
                console.log(this.lrs_error);
              }
            });
        },

        add_social: function(platform) {
            social_fn = {'facebook': this.get_facebook,
                         'twitter': this.get_twitter,
                         'youtube': this.get_youtube,
                         'github': this.get_github,
                         'trello': this.get_trello};

            console.log('add_social clicked for platform: ' + platform);
            console.log(social_fn[platform]);
            social_fn[platform]();
        },

        get_facebook: function() {
            // Facebook Auth-flow
            console.log('FB CLICKED');
            rf = this;

            // Auth and Login User
            FB.login(function(response) {
                if (response.status == 'connected') {
                    // Login Success
                    rf.social_account.platform = 'facebook';
                    rf.social_account.id = response.authResponse.userID;

                    console.log('got user: ' + rf.social_account.id);

                    FB.api(
                        "/"+rf.social_account.id+"/",
                        function(response) {
                            if (response && !response.erro) {
                                rf.social_account.name = response.name;
                                console.log('got users name: ' + response.name);

                                // We want this to occur *after* we get the user's name
                                // thus, we retreive thumbnail pic and finalise data here.
                                FB.api(
                                    "/"+rf.social_account.id+"/picture?redirect=false&height=20&width=20",
                                    function(response) {
                                        if (response && !response.error) {
                                            rf.social_account.thumbnail = response.data.url;
                                            console.log('got prof pic: ' + response.data.url);
                                            rf.social_accounts.push(rf.social_account);
                                            console.log(rf.social_account);
                                            rf.social_account = {platform: '', id: '', thumbnail: '', name: ''};
                                            rf.fb = true;
                                        }
                                    }
                                );
                            }
                        }
                    );

                } else if (response.status == 'not_authorized') {
                // Logged into FB, but not app
                } else {
                // unknown, not logged into fb
                }
            }, {scope: 'public_profile,email'});
        },

        get_twitter: function() {
            // TWitter Auth-flow

            this.social_account.platform = 'twitter';
            this.social_account.name = ' ';
            this.social_accounts.push(this.social_account);
            this.twitter_account_index = this.social_accounts.length - 1;

            this.social_account = this.reset_social_account();


            this.tw = true;

        },

        get_youtube: function() {
            // Youtube Auth-flow
            // Youtube api key: 968011825139-t9o0nbnnkq57vlm9n8vf9us12feo7dob.apps.googleusercontent.com
            var OAUTH2_CLIENT_ID = '968011825139-t9o0nbnnkq57vlm9n8vf9us12feo7dob.apps.googleusercontent.com';
            var OAUTH2_SCOPE = [
                'https://www.googleapis.com/auth/youtube'
            ];

            rf = this;

            gapi.load('client:auth', function() {
                gapi.auth.authorize({
                    client_id: OAUTH2_CLIENT_ID,
                    scope: OAUTH2_SCOPE,
                    immediate: false
                }, function (authResult) {
                    console.log('got youtube auth result');
                    console.log(authResult);
                    console.log(authResult && !authResult.error);
                    if (authResult && !authResult.error) {
                        //console.log('loa');
                        gapi.client.load('youtube', 'v3', function () {
                            console.log('attempting to grab channel ID');
                            var request = gapi.client.youtube.channels.list({
                                mine: true,
                                part: 'snippet,contentDetails'
                            } );

                            request.execute(function (resp) {
                                if (!resp.error) {
                                    rf.social_account.platform = 'youtube';
                                    rf.social_account.id = resp.items[0].id;
                                    console.log('got youtube ID:');
                                    console.log(rf.social_account.id);

                                    rf.social_account.name = resp.items[0].snippet.title;
                                    console.log('got user name:');
                                    console.log(rf.social_account.name);

                                    rf.social_account.thumbnail = resp.items[0].snippet.thumbnails.default.url;

                                    rf.social_accounts.push(rf.social_account);

                                    console.log('youtube social_account:');
                                    console.log(rf.social_account);

                                    rf.social_account = {platform: '', id: '', thumbnail: '', name: ''};
                                    rf.yt = true;
                                }
                                console.log(resp);
                            });
                        });
                    }
                });
            });
            //});
        },

        get_github: function() {
            // Github Auth-flow
            // Github API Key: 1bc5e54c677bee8b6b3a
            //TODO: Connect to pre-existing Github Auth through the toolkit

        },

        get_trello: function() {
            // Trello Auth-flow
            // Trello API Key: c908d424dda56c79d373f780a1ae26c7

            rf = this;

            console.log('Attempting trello auth');

            thumbnail_source = 'http://www.gravatar.com/avatar/';
            thumbnail_specs = '.jpg?s=20';

            Trello.authorize({
                type: "popup",
                expiration: "never", // Until user disconnects
                name: "CLAToolkit",
                persist: "true",
                success: function() {
                    console.log('trello auth success!');
                    console.log('attempting to grab user details');
                    Trello.rest("GET", "members/me", function(resp){
                        console.log('Got user details!');
                        console.log(resp);

                        rf.social_account.platform = 'trello';
                        rf.social_account.id = Trello.token(); // Id is user token (probs shouldn't do it here but yolo)
                        rf.social_account.name = resp.fullName;
                        rf.social_account.thumbnail = thumbnail_source + resp.gravatarHash + thumbnail_specs;

                        console.log('trello social account:');
                        console.log(rf.social_account);

                        rf.social_accounts.push(rf.social_account);
                        rf.social_account = rf.reset_social_account();
                        rf.tr = true;

                    })
                },
                error: function(response) {
                    console.log('trello auth failed...');
                    console.log(response);
                }
            });

        },

        reset_social_account: function() {
            return {platform: '', id: '', thumbnail: '', name: ''};
        },
        reset_form_errors: function() {
          return {user_form: {username: '', password: '', email:''}, profile_form: {
            fb_id: '',
            twitter_id: '',
            forum_id: '',
            google_account_name: '',
            github_account_name: '',
            trello_account_name: '',
            blog_id: '',
            diigo_id: ''
          }}
        },

        check_name: function(platform) {

            console.log(this.social_accounts[this.twitter_account_index]);

            if (platform == 'twitter') {
                // Find and Verify user
                console.log('checking name...');
                console.log('name is:');
                console.log(this.social_accounts[this.twitter_account_index].name);
            }
        }


    }


});


/******************************\
*                              *
*      Social Media SDK's      *
*                              *
\******************************/

/*--------------------------
        Facebook
 -------------------------*/
